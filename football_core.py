"""Shared core for the Football Club plugin and CLI.

Fetches data from football-data.org (free tier), caches it on disk, and formats it.
Uses only the Python standard library, so there is nothing to `pip install`.
"""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

API = "https://api.football-data.org/v4"
REGISTER_URL = "https://www.football-data.org/client/register"

_APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
_LOCAL = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
CONFIG_DIR = os.path.join(_APPDATA, "football-club")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CACHE_DIR = os.path.join(_LOCAL, "football-club", "cache")

# Club competitions included in football-data.org's free tier
LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "ELC": "Championship",
    "BSA": "Brasileirão",
}
COMPETITIONS = {**LEAGUES, "CL": "Champions League"}
SHORT_NAMES = {"CL": "UCL"}
CALENDAR_YEAR_LEAGUES = {"BSA"}  # seasons run January–December

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

LIVE = {"IN_PLAY", "PAUSED", "LIVE"}
DONE = {"FINISHED", "AWARDED"}
UPCOMING = {"SCHEDULED", "TIMED"}
OFF = {"POSTPONED", "SUSPENDED", "CANCELLED"}

STAGES = {
    "LEAGUE_STAGE": "League Phase",
    "GROUP_STAGE": "Group Stage",
    "PLAYOFFS": "Knockout Playoffs",
    "LAST_16": "Round of 16",
    "ROUND_OF_16": "Round of 16",
    "QUARTER_FINALS": "Quarter-finals",
    "SEMI_FINALS": "Semi-finals",
    "FINAL": "Final",
}

OUTCOME_ICON = {"W": "✅", "D": "➖", "L": "❌", None: "•"}


class FootballError(Exception):
    """An error whose message is safe to show to the user."""


class NoApiKey(FootballError):
    pass


class NoTeam(FootballError):
    pass


_overrides = {}


def configure(api_key=None, team=None):
    """Values from Flow Launcher's plugin settings; they win over env vars and the config file."""
    _overrides["api_key"] = (api_key or "").strip() or None
    _overrides["team"] = (team or "").strip() or None


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(**values):
    cfg = load_config()
    cfg.update({k: v for k, v in values.items() if v is not None})
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def api_key():
    return (_overrides.get("api_key")
            or os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
            or (load_config().get("api_key") or "").strip()
            or None)


def team_setting():
    return (_overrides.get("team")
            or os.environ.get("FOOTBALL_CLUB_TEAM", "").strip()
            or (load_config().get("team") or "").strip()
            or None)


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def fetch(path, cache_name, ttl):
    """GET an API path with an on-disk cache.

    `ttl` is seconds, or a function(data) -> seconds (shorter while a match is live).
    If the API fails, stale cached data is returned when available.
    """
    cache_file = os.path.join(CACHE_DIR, cache_name + ".json")
    cached = _read_json(cache_file)
    if cached is not None:
        age = time.time() - os.path.getmtime(cache_file)
        if age < (ttl(cached) if callable(ttl) else ttl):
            return cached

    key = api_key()
    if not key:
        raise NoApiKey("football-data.org API key is not set")

    req = urllib.request.Request(API + path, headers={"X-Auth-Token": key, "User-Agent": "football-club/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        if cached is not None:
            return cached
        messages = {
            400: "The API rejected the request (400)",
            403: "Invalid API key, or this competition isn't included in your football-data.org plan",
            404: "Not found (404)",
            429: "Too many requests. Wait a minute and try again",
        }
        raise FootballError(messages.get(e.code, f"API error {e.code}"))
    except (urllib.error.URLError, TimeoutError, OSError):
        if cached is not None:
            return cached
        raise FootballError("Can't reach football-data.org. Check your internet connection")

    _write_json(cache_file, data)
    return data


_DROP_WORDS = {"fc", "cf", "afc", "sc", "club", "ac"}


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    words = re.sub(r"[^a-z0-9]+", " ", text).split()
    return " ".join(w for w in words if w not in _DROP_WORDS) or " ".join(words)


def _match_score(query, team):
    names = [normalize(team.get(k, "")) for k in ("shortName", "name", "tla")]
    names = [n for n in names if n]
    if query in names:
        return 100
    if any(n.startswith(query) for n in names):
        return 80
    if any(query in n for n in names):
        return 60
    words = query.split()
    if words and all(any(w in n for n in names) for w in words):
        return 50
    return 0


def search_teams(query, limit=8):
    """Find clubs by name across the free-tier leagues (team lists are cached for a week)."""
    q = normalize(query)
    if not q:
        return []
    found, errors = {}, []
    for code in LEAGUES:
        try:
            teams = fetch(f"/competitions/{code}/teams", f"teams_{code}", 7 * 86400).get("teams", [])
        except NoApiKey:
            raise
        except FootballError as e:
            errors.append(e)
            continue
        for t in teams:
            score = _match_score(q, t)
            if score and (t["id"] not in found or found[t["id"]][0] < score):
                found[t["id"]] = (score, t, code)
        if any(s == 100 for s, _, _ in found.values()):
            break  # exact match: no need to load more leagues
    if not found and errors and len(errors) == len(LEAGUES):
        raise errors[0]
    ranked = sorted(found.values(), key=lambda x: (-x[0], x[1].get("name", "")))
    return [(t, code) for _, t, code in ranked[:limit]]


def current_team():
    """Return (team_details, league_code) for the favorite team setting."""
    setting = team_setting()
    if not setting:
        raise NoTeam("No favorite team selected")
    if setting.isdigit():
        team_id = int(setting)
    else:
        matches = search_teams(setting, limit=1)
        if not matches:
            raise FootballError(f"No club found for '{setting}'")
        team_id = matches[0][0]["id"]
    team = fetch(f"/teams/{team_id}", f"team_{team_id}", 86400)
    return team, league_of(team)


def league_of(team):
    running = [c.get("code") for c in team.get("runningCompetitions", [])]
    return next((code for code in LEAGUES if code in running), None)


def plays_in(team, code):
    return any(c.get("code") == code for c in team.get("runningCompetitions", []))


def season_for(league, now=None):
    now = now or datetime.now()
    if league in CALENDAR_YEAR_LEAGUES:
        return now.year
    return now.year if now.month >= 7 else now.year - 1


def _matches_ttl(data):
    return 60 if any(m.get("status") in LIVE for m in data.get("matches", [])) else 600


def team_matches(team, league):
    season = season_for(league)
    data = fetch(f"/teams/{team['id']}/matches?season={season}", f"matches_{team['id']}_{season}", _matches_ttl)
    return sorted(data.get("matches", []), key=lambda m: m.get("utcDate", ""))


def split_matches(matches):
    live = [m for m in matches if m.get("status") in LIVE]
    done = [m for m in matches if m.get("status") in DONE]
    upcoming = [m for m in matches if m.get("status") in UPCOMING | OFF]
    return live, done, upcoming


def standings(code, team_id=None):
    data = fetch(f"/competitions/{code}/standings", f"standings_{code}", 1800)
    tables = [s for s in data.get("standings", []) if s.get("type", "TOTAL") == "TOTAL"]
    if not tables:
        return [], None
    chosen = next((s for s in tables if any(r.get("team", {}).get("id") == team_id for r in s.get("table", []))),
                  tables[0])
    return chosen.get("table", []), chosen.get("group") or chosen.get("stage")


def scorers(code, limit=15):
    # Fetch a longer list once (also used for player stats) and slice it for display.
    rows = fetch(f"/competitions/{code}/scorers?limit=50", f"scorers_{code}", 3600).get("scorers", [])
    return rows[:limit]


def player_stats(player, codes):
    """Season goal stats for a player from the competitions' scorer lists: [(code, scorer_row)].

    Only players who have scored appear in these lists, so an empty result just means
    no goals recorded in these competitions (or not in the top 50).
    """
    out = []
    for code in codes:
        try:
            rows = scorers(code, limit=50)
        except FootballError:
            continue
        row = next((r for r in rows if _same_player(r.get("player") or {}, player)), None)
        if row:
            out.append((code, row))
    return out


def _same_player(a, b):
    if a.get("id") is not None and b.get("id") is not None:
        return a["id"] == b["id"]
    return bool(a.get("name")) and normalize(a.get("name")) == normalize(b.get("name"))


def fmt_date(iso):
    try:
        d = date.fromisoformat((iso or "")[:10])
    except ValueError:
        return None
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def find_player(team, query):
    """Exact (normalized) name match, used when a player is picked from the squad list."""
    q = normalize(query)
    return next((p for p in team.get("squad") or [] if normalize(p.get("name")) == q), None)


def team_competitions(team, league):
    return [c for c in (league, "CL") if c and (c == league or plays_in(team, c))]


def table_row(table, team_id):
    return next((r for r in table if r.get("team", {}).get("id") == team_id), None)


_POSITION_ORDER = [("goalkeeper", 0), ("back", 1), ("defen", 1), ("midfield", 2),
                   ("wing", 3), ("forward", 3), ("striker", 3), ("offence", 3), ("attack", 3)]


def position_rank(position):
    p = (position or "").lower()
    return next((rank for word, rank in _POSITION_ORDER if word in p), 4)


def position_group(position):
    return ["Goalkeepers", "Defenders", "Midfielders", "Forwards", "Others"][position_rank(position)]


def age(date_of_birth, today=None):
    try:
        dob = date.fromisoformat((date_of_birth or "")[:10])
    except ValueError:
        return None
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def squad(team, query=""):
    players = team.get("squad") or []
    q = normalize(query)
    if q:
        players = [p for p in players if q in normalize(p.get("name", ""))]
    return sorted(players, key=lambda p: (position_rank(p.get("position")), p.get("name", "")))


def team_name(team):
    team = team or {}
    return team.get("shortName") or team.get("name") or team.get("tla") or "?"


def to_local(utc):
    return datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone()


def fmt_datetime(utc):
    dt = to_local(utc)
    return f"{DAYS[dt.weekday()]} {dt.day} {MONTHS[dt.month - 1]}, {dt:%H:%M}"


def comp_name(code):
    return COMPETITIONS.get(code, code or "")


def comp_label(match):
    comp = match.get("competition") or {}
    code = comp.get("code")
    return SHORT_NAMES.get(code) or COMPETITIONS.get(code) or comp.get("name") or ""


def round_label(match):
    stage = match.get("stage") or ""
    code = (match.get("competition") or {}).get("code")
    if match.get("matchday") and stage in ("REGULAR_SEASON", "LEAGUE_STAGE", "GROUP_STAGE", ""):
        return f"{'Matchweek' if code in LEAGUES else 'Matchday'} {match['matchday']}"
    return STAGES.get(stage, stage.replace("_", " ").title())


def score_text(match):
    score = match.get("score") or {}
    ft = score.get("fullTime") or {}
    home, away = ft.get("home"), ft.get("away")
    if home is None or away is None:
        return "vs"
    text = f"{home}–{away}"
    pens = score.get("penalties") or {}
    if score.get("duration") == "PENALTY_SHOOTOUT" and pens.get("home") is not None:
        text += f" ({pens['home']}–{pens['away']} pens)"
    return text


def match_title(match):
    return f"{team_name(match.get('homeTeam'))} {score_text(match)} {team_name(match.get('awayTeam'))}"


def outcome(match, team_id):
    """'W', 'D' or 'L' for the given team, or None if not finished."""
    winner = (match.get("score") or {}).get("winner")
    if winner == "DRAW":
        return "D"
    if winner not in ("HOME_TEAM", "AWAY_TEAM"):
        return None
    is_home = (match.get("homeTeam") or {}).get("id") == team_id
    return "W" if (winner == "HOME_TEAM") == is_home else "L"


def match_subtitle(match):
    parts = [comp_label(match), round_label(match), fmt_datetime(match["utcDate"])]
    status = match.get("status")
    if status in OFF:
        parts.append(status.title())
    return " · ".join(p for p in parts if p)


def match_copy_text(match):
    return f"{match_title(match)} · {match_subtitle(match)}"


def search_url(text):
    from urllib.parse import quote_plus
    return "https://www.google.com/search?q=" + quote_plus(text)

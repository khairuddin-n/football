"""Flow Launcher plugin: fixtures, results, standings, top scorers and squad for your favorite club.

Flow Launcher runs this file with one JSON argument, e.g.
{"method": "query", "parameters": ["table"], "settings": {"apiKey": "...", "team": "Barcelona"}},
and reads the JSON result from stdout.
"""

import json
import os
import sys
import webbrowser

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)
import football_core as fc  # noqa: E402

ICON = "Images\\app.png"


def _load_manifest():
    try:
        with open(os.path.join(PLUGIN_DIR, "plugin.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def action_keyword():
    """The keyword the user actually set in Flow Launcher (it can be changed from the default)."""
    manifest = _load_manifest()
    default = manifest.get("ActionKeyword", "fc")
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return default
    try:
        with open(os.path.join(appdata, "FlowLauncher", "Settings", "Settings.json"), encoding="utf-8-sig") as f:
            plugins = json.load(f).get("PluginSettings", {}).get("Plugins", {})
        keywords = plugins.get(manifest.get("ID", ""), {}).get("ActionKeywords") or []
        return next((k for k in keywords if k and k != "*"), default)
    except (OSError, ValueError, AttributeError):
        return default


KEYWORD = action_keyword()


def item(title, subtitle="", url=None, query=None, copy=None, settings_change=None, preview=None):
    """One result row. Enter opens `url` or switches Flow to `query`; Ctrl+C copies `copy`.
    `preview` is text for Flow's preview panel (toggle it with Flow's preview hotkey)."""
    result = {"Title": title, "SubTitle": subtitle, "IcoPath": ICON, "CopyText": copy or title}
    if preview:
        result["Preview"] = {"Description": preview}
    if query is not None:
        result["JsonRPCAction"] = {
            "method": "Flow.Launcher.ChangeQuery",
            "parameters": [f"{KEYWORD} {query}".rstrip() + " " if query else f"{KEYWORD} ", True],
            "dontHideAfterAction": True,
        }
    elif url:
        result["JsonRPCAction"] = {"method": "open_url", "parameters": [url]}
    if settings_change:
        result["SettingsChange"] = settings_change
    return result


def ranked(items):
    """Keep our order: Flow sorts by score."""
    for i, it in enumerate(items):
        it["Score"] = 10000 - i * 10
    return items


def match_item(m, team_id, prefix=""):
    status = m.get("status")
    if status in fc.LIVE:
        icon = "🔴 LIVE"
    elif status in fc.DONE:
        icon = fc.OUTCOME_ICON[fc.outcome(m, team_id)]
    else:
        icon = "📅"
    title = fc.match_title(m)
    return item(f"{icon}  {prefix}{title}", fc.match_subtitle(m),
                url=fc.search_url(title.replace("–", "-")), copy=fc.match_copy_text(m))


def standings_row_text(r):
    return (f"Played {r['playedGames']} · W{r['won']} D{r['draw']} L{r['lost']} · "
            f"Goals {r['goalsFor']}:{r['goalsAgainst']} ({r['goalDifference']:+d})")


def view_summary(team, league):
    tid = team["id"]
    live, done, upcoming = fc.split_matches(fc.team_matches(team, league))
    items = [match_item(m, tid) for m in live]
    if upcoming:
        items.append(match_item(upcoming[0], tid, prefix="Next: "))
        items[-1]["Title"] = items[-1]["Title"].replace("📅", "⏭", 1)
    if done:
        items.append(match_item(done[-1], tid, prefix="Last: "))
    if league:
        try:
            row = fc.table_row(fc.standings(league, tid)[0], tid)
            if row:
                items.append(item(f"🏆  #{row['position']} in {fc.comp_name(league)} · {row['points']} pts",
                                  standings_row_text(row), query="table"))
        except fc.FootballError:
            pass
    items += [
        item("📅  Fixtures", "Upcoming matches", query="fixtures"),
        item("📋  Results", "Recent results", query="results"),
    ]
    if league:
        items.append(item(f"🏆  {fc.comp_name(league)} table", "", query="table"))
    if fc.plays_in(team, "CL"):
        items.append(item("⭐  Champions League table", "", query="cl"))
    if league:
        items.append(item(f"⚽  {fc.comp_name(league)} top scorers", "", query="scorers"))
    if fc.plays_in(team, "CL"):
        items.append(item("⚽  Champions League top scorers", "", query="cl scorers"))
    items += [
        item("👥  Squad", "Players and coach", query="squad"),
        item("🔁  Change team", f"Current: {team.get('name', fc.team_name(team))}", query="team"),
    ]
    return items


def view_fixtures(team, league, n=10):
    live, _, upcoming = fc.split_matches(fc.team_matches(team, league))
    rows = live + upcoming[:n]
    return [match_item(m, team["id"]) for m in rows] or [item("No upcoming matches")]


def view_results(team, league, n=10):
    _, done, _ = fc.split_matches(fc.team_matches(team, league))
    return [match_item(m, team["id"]) for m in reversed(done[-n:])] or [item("No results this season yet")]


def view_table(team, code):
    if not code:
        return [item("No league found for this team in the free tier")]
    table, _ = fc.standings(code, team["id"])
    if not table:
        return [item("Standings not available yet")]
    name = fc.comp_name(code)
    out = []
    for r in table:
        mine = r.get("team", {}).get("id") == team["id"]
        title = f"{r['position']:>2}. {'👉 ' if mine else ''}{fc.team_name(r.get('team'))} — {r['points']} pts"
        out.append(item(title, standings_row_text(r), url=fc.search_url(f"{name} table"),
                        copy=f"{r['position']}. {fc.team_name(r.get('team'))} — {r['points']} pts"))
    return out


def view_scorers(team, code):
    if not code:
        return [item("No league found for this team in the free tier")]
    rows = fc.scorers(code)
    if not rows:
        return [item("Top scorers not available yet")]
    out = []
    for i, s in enumerate(rows, 1):
        player = (s.get("player") or {}).get("name", "?")
        mine = (s.get("team") or {}).get("id") == team["id"]
        extras = [fc.team_name(s.get("team"))]
        if s.get("assists") is not None:
            extras.append(f"{s['assists']} assists")
        if s.get("penalties"):
            extras.append(f"{s['penalties']} pens")
        if s.get("playedMatches"):
            extras.append(f"{s['playedMatches']} apps")
        title = f"{i:>2}. {'👉 ' if mine else ''}{player} — {s.get('goals', 0)} goals"
        out.append(item(title, " · ".join(extras), url=fc.search_url(player),
                        copy=f"{player} ({fc.team_name(s.get('team'))}) — {s.get('goals', 0)} goals"))
    return out


def player_lines(team, p, stats):
    """Detail lines for a player, used by the preview panel and the detail page."""
    a = fc.age(p.get("dateOfBirth"))
    born = fc.fmt_date(p.get("dateOfBirth"))
    lines = [p.get("name", "?"), "",
             f"Club: {team.get('name', fc.team_name(team))}",
             f"Position: {p.get('position') or '-'}",
             f"Nationality: {p.get('nationality') or '-'}"]
    if born:
        lines.append(f"Born: {born}" + (f" ({a} yrs)" if a is not None else ""))
    lines.append("")
    if stats:
        lines.append("This season")
        for code, s in stats:
            lines.append(f"  {fc.comp_name(code)}: {stat_text(s)}")
    else:
        lines.append("No goals recorded this season")
    return lines


def stat_text(s):
    parts = [f"{s.get('goals', 0)} goals"]
    if s.get("assists") is not None:
        parts.append(f"{s['assists']} assists")
    if s.get("penalties"):
        parts.append(f"{s['penalties']} pens")
    if s.get("playedMatches"):
        parts.append(f"{s['playedMatches']} apps")
    return " · ".join(parts)


def view_player(team, league, p):
    stats = fc.player_stats(p, fc.team_competitions(team, league))
    name = p.get("name", "?")
    a = fc.age(p.get("dateOfBirth"))
    born = fc.fmt_date(p.get("dateOfBirth"))
    preview = "\n".join(player_lines(team, p, stats))
    out = [
        item(f"👤  {name}", f"{p.get('position') or '-'} · {p.get('nationality') or '-'}",
             copy=f"{name} ({p.get('position') or '-'}, {p.get('nationality') or '-'})", preview=preview),
    ]
    if born:
        out.append(item(f"🎂  Born {born}" + (f" · {a} yrs" if a is not None else ""), "", preview=preview))
    for code, s in stats:
        out.append(item(f"⚽  {fc.comp_name(code)}: {s.get('goals', 0)} goals", stat_text(s),
                        copy=f"{name} — {fc.comp_name(code)}: {stat_text(s)}", preview=preview))
    if not stats:
        out.append(item("⚽  No goals recorded this season", "Based on the competitions' top-scorer lists",
                        preview=preview))
    out += [
        item("🔎  Search the web", f"{name} {fc.team_name(team)}",
             url=fc.search_url(f"{name} {fc.team_name(team)}")),
        item("↩  Back to squad", "", query="squad"),
    ]
    return out


def view_squad(team, league, query=""):
    exact = fc.find_player(team, query) if query else None
    if exact:
        return view_player(team, league, exact)
    players = fc.squad(team, query)
    out = []
    coach = team.get("coach") or {}
    if coach.get("name") and not query:
        out.append(item(f"🧑‍💼  {coach['name']} — Head coach", coach.get("nationality") or "",
                        url=fc.search_url(coach["name"])))
    for p in players:
        a = fc.age(p.get("dateOfBirth"))
        details = [p.get("position") or fc.position_group(p.get("position")), p.get("nationality") or ""]
        if a is not None:
            details.append(f"{a} yrs")
        out.append(item(f"{p.get('name', '?')}", " · ".join(d for d in details if d),
                        query=f"squad {p.get('name', '')}",
                        copy=f"{p.get('name', '?')} ({p.get('position') or '-'}, {p.get('nationality') or '-'})",
                        preview="\n".join(player_lines(team, p, []) [:-2])))
    if not out:
        msg = f"No player matching '{query}'" if query else "Squad data not available for this team"
        out.append(item(msg))
    return out


def view_team_picker(query):
    if not query:
        return [item("Type a club name", f"e.g. {KEYWORD} team barcelona, {KEYWORD} team arsenal")]
    found = fc.search_teams(query)
    if not found:
        return [item(f"No club found for '{query}'",
                     "Only clubs from the free-tier leagues are available")]
    return [item(f"⚽  {t.get('name')}", f"{fc.comp_name(code)} · press Enter to make it your team",
                 query="", settings_change={"team": t.get("name")})
            for t, code in found]


def route(text):
    words = text.split()
    head, rest = (words[0] if words else ""), " ".join(words[1:])

    if not fc.api_key():
        raise fc.NoApiKey("football-data.org API key is not set")
    if head == "team":
        return view_team_picker(rest)

    team, league = fc.current_team()
    if not text:
        return view_summary(team, league)
    if text in ("fixtures", "next", "upcoming"):
        return view_fixtures(team, league)
    if text in ("results", "last"):
        return view_results(team, league)
    if text in ("table", "standings"):
        return view_table(team, league)
    if text in ("cl", "ucl", "cl table", "ucl table"):
        return view_table(team, "CL")
    if text in ("scorers", "top"):
        return view_scorers(team, league)
    if text in ("cl scorers", "ucl scorers", "scorers cl", "scorers ucl"):
        return view_scorers(team, "CL")
    if head == "squad":
        return view_squad(team, league, rest)

    commands = ["fixtures", "results", "table", "cl", "scorers", "cl scorers", "squad", "team"]
    hints = [c for c in commands if c.startswith(text)]
    if hints:
        return [item(f"↪  {h}", "Press Enter", query=h) for h in hints]
    return [item("Unknown command", "Try: fixtures, results, table, cl, scorers, cl scorers, squad, team", query="")]


def query(text):
    text = " ".join(text.lower().split())
    try:
        return ranked(route(text))
    except fc.NoApiKey:
        return [item("🔑  Set your football-data.org API key",
                     "Flow Settings → Plugins → Football Club · Press Enter to get a free key",
                     url=fc.REGISTER_URL)]
    except fc.NoTeam:
        return [item("⚽  Choose your favorite club", f"Type: {KEYWORD} team <name>, e.g. {KEYWORD} team barcelona",
                     query="team")]
    except fc.FootballError as e:
        return [item("⚠️  " + str(e), "Cached data will be shown again once this is resolved")]


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else '{"method": "query", "parameters": [""]}'
    request = json.loads(raw)
    method, params = request.get("method"), request.get("parameters") or []
    settings = request.get("settings") or {}
    fc.configure(api_key=settings.get("apiKey"), team=settings.get("team"))
    if method == "query":
        print(json.dumps({"result": query(params[0] if params else "")}))
    elif method == "open_url" and params:
        webbrowser.open(params[0])


if __name__ == "__main__":
    main()

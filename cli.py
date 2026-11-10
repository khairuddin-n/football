"""Football Club CLI: your club's fixtures, results, standings, top scorers and squad.

Usage (the command name depends on how you installed it, e.g. `fc` or `football`):
  fc                 summary (live, next, last, league position)
  fc fixtures        upcoming matches
  fc results         recent results + form
  fc table           domestic league table
  fc cl              Champions League table
  fc scorers         league top scorers
  fc cl scorers      Champions League top scorers
  fc squad [name]    squad, optionally filtered by player name
  fc team <name>     choose your favorite club
  fc setup           save your football-data.org API key
"""

import getpass
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import football_core as fc  # noqa: E402

CMD = os.environ.get("FOOTBALL_CLUB_CMD", "fc")


if os.name == "nt":
    os.system("")  # enable ANSI colors in older Windows consoles
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else str(text)


BOLD, DIM = "1", "2"
ACCENT, GOLD = "38;2;225;60;120", "38;2;237;187;0"
GREEN, RED, GREY = "38;2;166;227;161", "38;2;243;139;168", "38;2;147;153;178"
HL = "48;2;40;44;80"
OUT_COLOR = {"W": GREEN, "D": GREY, "L": RED, None: GREY}


def width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text, n, right=False):
    gap = max(0, n - width(text))
    return (" " * gap + text) if right else (text + " " * gap)


def header(title):
    print()
    print(c(" ▌", ACCENT) + c(f" {title} ", BOLD + ";" + GOLD))
    print()


def mark(line, mine):
    return c(line, BOLD + ";" + GOLD + ";" + HL) if mine else line


def print_match(m, team_id):
    status = m.get("status")
    if status in fc.LIVE:
        tag = c(" LIVE ", "1;41;97")
    elif status in fc.DONE:
        o = fc.outcome(m, team_id)
        tag = c(f" {o} ", f"1;{OUT_COLOR[o]}") if o else "   "
    else:
        tag = c(" ⏭ ", GOLD)
    home, away = m.get("homeTeam", {}), m.get("awayTeam", {})
    name_h = c(fc.team_name(home), BOLD) if home.get("id") == team_id else fc.team_name(home)
    name_a = c(fc.team_name(away), BOLD) if away.get("id") == team_id else fc.team_name(away)
    score = fc.score_text(m)
    score = c(score, BOLD + ";" + GOLD) if score != "vs" else c("vs", DIM)
    print(f"  {tag} {name_h} {score} {name_a}")
    print(c(f"       {fc.match_subtitle(m)}", GREY))


def cmd_summary(team, league):
    tid = team["id"]
    live, done, upcoming = fc.split_matches(fc.team_matches(team, league))
    header(team.get("name") or fc.team_name(team))
    for m in live:
        print_match(m, tid)
    if upcoming:
        print(c("  Next", DIM))
        print_match(upcoming[0], tid)
    if done:
        print(c("  Last", DIM))
        print_match(done[-1], tid)
    if league:
        try:
            row = fc.table_row(fc.standings(league, tid)[0], tid)
            if row:
                print(f"\n  🏆 {c('#' + str(row['position']), BOLD + ';' + GOLD)} in {fc.comp_name(league)} · "
                      f"{c(row['points'], BOLD)} pts · played {row['playedGames']} · "
                      f"W{row['won']} D{row['draw']} L{row['lost']}")
        except fc.FootballError:
            pass
    print(c("\n  fixtures · results · table · cl · scorers · cl scorers · squad · team", GREY))
    print()


def cmd_fixtures(team, league, n=8):
    live, _, upcoming = fc.split_matches(fc.team_matches(team, league))
    header(f"{fc.team_name(team)} fixtures")
    rows = live + upcoming[:n]
    if not rows:
        print("  No upcoming matches.")
    for m in rows:
        print_match(m, team["id"])
    print()


def cmd_results(team, league, n=8):
    _, done, _ = fc.split_matches(fc.team_matches(team, league))
    header(f"{fc.team_name(team)} results")
    if not done:
        print("  No results this season yet.")
    for m in reversed(done[-n:]):
        print_match(m, team["id"])
    if done:
        form = "".join(c(fc.outcome(m, team["id"]) or "-", f"1;{OUT_COLOR[fc.outcome(m, team['id'])]}")
                       for m in done[-5:])
        print(f"\n  Form (last 5): {form}")
    print()


def cmd_table(team, code):
    if not code:
        print("\n  No league found for this team in the free tier.\n")
        return
    table, group = fc.standings(code, team["id"])
    suffix = f" · {fc.STAGES.get(group, group.replace('_', ' ').title())}" if group and code == "CL" else ""
    header(f"{fc.comp_name(code)} table{suffix}")
    if not table:
        print("  Standings not available yet.\n")
        return
    print(c(f"  {'#':>3}  {pad('Team', 22)} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'Goals':>7} {'GD':>4} {'Pts':>4}", DIM))
    for r in table:
        t = r.get("team", {})
        line = (f"  {r['position']:>3}  {pad(fc.team_name(t)[:22], 22)} {r['playedGames']:>3} "
                f"{r['won']:>3} {r['draw']:>3} {r['lost']:>3} "
                f"{str(r['goalsFor']) + ':' + str(r['goalsAgainst']):>7} {r['goalDifference']:>+4} {r['points']:>4} ")
        print(mark(line, t.get("id") == team["id"]))
    print()


def cmd_scorers(team, code):
    if not code:
        print("\n  No league found for this team in the free tier.\n")
        return
    rows = fc.scorers(code)
    header(f"{fc.comp_name(code)} top scorers")
    if not rows:
        print("  Top scorers not available yet.\n")
        return
    print(c(f"  {'#':>3}  {pad('Player', 24)} {pad('Team', 16)} {'G':>3} {'A':>3} {'Pen':>4}", DIM))
    for i, s in enumerate(rows, 1):
        t = s.get("team", {})
        assists = s.get("assists") if s.get("assists") is not None else "-"
        line = (f"  {i:>3}  {pad((s.get('player') or {}).get('name', '?')[:24], 24)} "
                f"{pad(fc.team_name(t)[:16], 16)} {s.get('goals', 0):>3} {assists:>3} {s.get('penalties') or 0:>4} ")
        print(mark(line, t.get("id") == team["id"]))
    print()


def cmd_player(team, league, p):
    stats = fc.player_stats(p, fc.team_competitions(team, league))
    header(p.get("name", "?"))
    a = fc.age(p.get("dateOfBirth"))
    born = fc.fmt_date(p.get("dateOfBirth"))
    rows = [("Club", team.get("name") or fc.team_name(team)), ("Position", p.get("position") or "-"),
            ("Nationality", p.get("nationality") or "-")]
    if born:
        rows.append(("Born", born + (f" ({a} yrs)" if a is not None else "")))
    for k, v in rows:
        print(f"  {c(pad(k, 12), DIM)} {v}")
    print()
    if stats:
        print(c("  This season", BOLD + ";" + ACCENT))
        for code, s in stats:
            assists = s.get("assists") if s.get("assists") is not None else "-"
            print(f"    {pad(fc.comp_name(code), 18)} {c(s.get('goals', 0), BOLD + ';' + GOLD)} goals · "
                  f"{assists} assists · {s.get('playedMatches') or '-'} apps")
    else:
        print(c("  No goals recorded this season", GREY))
    print()


def cmd_squad(team, league, query=""):
    exact = fc.find_player(team, query) if query else None
    if exact:
        return cmd_player(team, league, exact)
    players = fc.squad(team, query)
    header(f"{fc.team_name(team)} squad" + (f" · '{query}'" if query else ""))
    coach = team.get("coach") or {}
    if coach.get("name") and not query:
        print(f"  {c('Head coach', DIM)}  {c(coach['name'], BOLD)}  {c(coach.get('nationality') or '', GREY)}\n")
    if not players:
        print(f"  No player matching '{query}'.\n" if query else "  Squad data not available for this team.\n")
        return
    group = None
    for p in players:
        g = fc.position_group(p.get("position"))
        if g != group:
            group = g
            print(c(f"  {g}", BOLD + ";" + ACCENT))
        a = fc.age(p.get("dateOfBirth"))
        print(f"    {pad(p.get('name', '?')[:28], 28)} {pad((p.get('position') or '')[:20], 20)} "
              f"{pad((p.get('nationality') or '')[:16], 16)} {c(f'{a} yrs' if a is not None else '', GREY)}")
    print()


def cmd_team(query):
    if not query:
        current = fc.team_setting()
        print(f"\nCurrent club: {current or '(none)'}")
        query = input("Club name: ").strip()
        if not query:
            return
    found = fc.search_teams(query)
    if not found:
        print(f"\nNo club found for '{query}'. Only clubs from the free-tier leagues are available.\n")
        return
    if len(found) == 1 or fc.normalize(found[0][0].get("shortName", "")) == fc.normalize(query):
        choice = found[0]
    else:
        print()
        for i, (t, code) in enumerate(found, 1):
            print(f"  {i}. {t.get('name')}  {c(fc.comp_name(code), GREY)}")
        pick = input("\nPick a number (Enter = 1): ").strip() or "1"
        if not pick.isdigit() or not 1 <= int(pick) <= len(found):
            print("Cancelled.")
            return
        choice = found[int(pick) - 1]
    fc.save_config(team=choice[0].get("name"))
    print(c(f"\nFavorite club set to {choice[0].get('name')}", GREEN) + "\n")


def cmd_setup():
    print(f"\nGet a free API key at {fc.REGISTER_URL}")
    print("The key is sent to your email. Paste it below (it stays hidden while you type or paste).\n")
    key = getpass.getpass("API key: ").strip()
    if not key:
        print("Cancelled, nothing was saved.")
        return
    fc.save_config(api_key=key)
    print(c(f"Saved to {fc.CONFIG_FILE}", GREEN) + "\n")


def run(text):
    words = text.split()
    head, rest = (words[0] if words else ""), " ".join(words[1:])
    if text in ("help", "-h", "--help"):
        print(__doc__.replace("fc ", CMD + " "))
        return
    if head == "setup":
        return cmd_setup()
    if not fc.api_key():
        raise fc.NoApiKey("football-data.org API key is not set")
    if head == "team":
        return cmd_team(rest)

    team, league = fc.current_team()
    if not text:
        cmd_summary(team, league)
    elif text in ("fixtures", "next", "upcoming"):
        cmd_fixtures(team, league)
    elif text in ("results", "last"):
        cmd_results(team, league)
    elif text in ("table", "standings"):
        cmd_table(team, league)
    elif text in ("cl", "ucl", "cl table", "ucl table"):
        cmd_table(team, "CL")
    elif text in ("scorers", "top"):
        cmd_scorers(team, league)
    elif text in ("cl scorers", "ucl scorers", "scorers cl", "scorers ucl"):
        cmd_scorers(team, "CL")
    elif head == "squad":
        cmd_squad(team, league, rest)
    else:
        print(f"Unknown command '{text}'.\n" + __doc__.replace("fc ", CMD + " "))
        return 1


def main(argv):
    text = " ".join(a.lower() for a in argv).strip()
    try:
        return run(text) or 0
    except fc.NoApiKey:
        print(c(f"\n🔑 API key is not set. Run: {CMD} setup\n", GOLD))
    except fc.NoTeam:
        print(c(f"\n⚽ No favorite club yet. Run: {CMD} team <name>, e.g. {CMD} team barcelona\n", GOLD))
    except fc.FootballError as e:
        print(c(f"\n⚠️  {e}\n", RED))
    except (KeyboardInterrupt, EOFError):
        return 130
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

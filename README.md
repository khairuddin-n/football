# Football Club

Your favorite club's fixtures, results, standings, top scorers and squad, right in
[Flow Launcher](https://www.flowlauncher.com) and your terminal.
Data from [football-data.org](https://www.football-data.org) (free tier). Times are shown in your local time zone.

## Features

| Flow Launcher | What you get |
|---|---|
| `fc` | Live match, next match, last result, league position, menu |
| `fc fixtures` | Upcoming matches (league + Champions League) |
| `fc results` | Recent results |
| `fc table` | Domestic league table, your club highlighted |
| `fc cl` | Champions League table |
| `fc scorers` / `fc cl scorers` | Top scorers |
| `fc squad [name]` | Squad and head coach, optionally filtered by player name |
| `fc team <name>` | Choose your favorite club |

- **Enter** on a match or player opens a web search for more details.
- **Ctrl+C** on any result copies it (e.g. to share a fixture in a chat).

## Supported clubs

Clubs from the leagues in football-data.org's free tier: Premier League, La Liga, Serie A,
Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Championship and Brasileirão,
plus the UEFA Champions League. Domestic cups are not included in the free tier.

## Setup

1. Get a free API key at https://www.football-data.org/client/register (sent to your email).
2. In Flow Launcher: **Settings → Plugins → Football Club**, paste your API key and type your club
   (e.g. `Barcelona`). Or type `fc team barcelona` and press Enter.

Your API key is stored locally and only sent to football-data.org. Don't share it.

### Terminal command (optional, Windows)

```powershell
.\install.ps1                  # command: fc
.\install.ps1 -Command ball    # or choose your own name
```

The installer installs Python if needed, creates the command, links the plugin into Flow Launcher,
and asks for your API key and club. The terminal command has its own settings
(`fc setup`, `fc team <name>`), stored in `%APPDATA%\football-club\config.json`.
Flow Launcher uses its own settings first and falls back to this file.

## Rate limits & caching

The free tier allows 10 requests per minute, so data is cached:
matches 10 min (1 min while a match is live), tables 30 min, scorers 1 h, squad 1 day,
club lists 1 week. If the API can't be reached, the last cached data is shown.
Live scores on the free tier may be slightly delayed.

The first club search loads the club lists of several leagues, so on first use you may briefly
hit the limit ("Too many requests"). Wait a minute and try again; after that the lists are cached.

## Files

- `football_core.py`: API client, cache and formatting (shared)
- `main.py`, `plugin.json`, `SettingsTemplate.yaml`: Flow Launcher plugin
- `cli.py`, `install.ps1`: terminal command

## License

[MIT](LICENSE). Not affiliated with football-data.org or any football club.

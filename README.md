# Betting Algorithm V6 — Repo Ready + CI + UEFA + Pipeline

Dieses Repo ist so aufbereitet, dass du es nach dem Entpacken direkt in ein Git-Repository schieben kannst.

## Aktueller Scope

### Football / Soccer
Live-Schiene:
- Bundesliga (`D1`)
- 2. Bundesliga (`D2`)
- Premier League (`E0`)
- La Liga (`SP1`)
- Serie A (`I1`)
- Ligue 1 (`F1`)
- Primeira Liga (`P1`)
- Eredivisie (`N1`)
- Champions League (`UCL`) via `football/uefa_live.py`
- Europa League (`UEL`) via `football/uefa_live.py`
- Conference League (`UECL`) via `football/uefa_live.py`

Die beiden zusätzlichen ersten Ligen aus Portugal und den Niederlanden sind jetzt auch im aktiven Domestic-Runner `football/cron_live.py` verdrahtet und nicht nur im Trainingspfad dokumentiert.

**Bewusst entfernt:** Championship / `E1`

Football-Märkte:
- 1X2
- Double Chance
- Over/Under Totals
- Player Props (Over/Under-Basis für Shots, Shots on Target, Assists, Passes, Tackles, Cards — abhängig von API-/Bookmaker-Verfügbarkeit)

### Basketball
- NBA
- EuroLeague

Basketball-Märkte:
- Moneyline
- Spread
- Totals
- Player Props (NBA: Points, Rebounds, Assists, Threes)

### American Football
- NFL

NFL-Märkte:
- Moneyline
- Spread
- Totals
- Player Props (Pass Yards, Pass TDs, Rush Yards, Receiving Yards, Receptions)

### Tennis
Tennis ist turnierbasiert implementiert und fokussiert standardmäßig auf Match Winner / H2H.
Vorkonfiguriert sind ATP/WTA Indian Wells, Miami, Madrid, Rom, Wimbledon und US Open.


## V6 Neu
- Champions League im aktiven UEFA-Scope
- automatischer UEFA-Teamwetten-Settlement-Pfad für Football über CSV + API-Sports-Fallback
- zentraler Pipeline-Runner mit `daily`, `weekly`, `uefa`, `props`, `full`
- manuelle Team-Settlement-Stores für EuroLeague/Tennis und generischer Team-Settler
- einfaches Retraining für EuroLeague/Tennis auf Basis settled Bets
- robusteres Player-Matching für Prop-Settlement

## Nicht im aktuellen Scope
- Championship
- NHL / MLB / WNBA
- Same Game Parlays
- In-Play Repricing

## Wichtige Runner
Beispiel für den Domestic-Runner mit allen aktiven Liga-Codes:

```bash
python football/cron_live.py --leagues D1 D2 E0 SP1 I1 F1 P1 N1
```

- `python football/cron_live.py --help`
- `python football/uefa_live.py --help`
- `python nba/cron_live.py --help`
- `python euroleague/cron_live.py --help`
- `python nfl/cron_live.py --help`
- `python tennis/cron_live.py --help`
- `python football/cron_props.py --help`
- `python nba/cron_props.py --help`
- `python nfl/cron_props.py --help`


## Prop-Settlement-Pipeline
Die Props-Schiene kann jetzt nicht nur Bets erzeugen, sondern auch automatisch abrechnen.

Ablauf:
- offene Props aus `data/tracked_bets/active_bets.jsonl` laden
- nach Spielende Stats auflösen
- zuerst manuelle Runtime-Dateien unter `data/settlement/manual/*_props_stats.json` prüfen
- danach optional API-Sports für NBA/NFL/Fußball abfragen
- Win/Loss/Push/Void berechnen und inkl. tatsächlichem Stat-Wert im Tracker speichern
- ungelöste Fälle nach `data/settlement/unresolved/*_props_unresolved.jsonl` schreiben

Wichtige Commands:
- `python shared/settle_player_props.py --help`
- `python football/settle_props.py --help`
- `python nba/settle_props.py --help`
- `python nfl/settle_props.py --help`

Beispiele:
```bash
python football/settle_props.py --manual-only
python nba/settle_props.py --settle-after-hours 5
python nfl/settle_props.py --max-bets 20
python shared/settle_player_props.py --sport all
```

Für automatische API-Auflösung optional in `secrets/.env` setzen:
```bash
APISPORTS_KEY=...
```

## Setup
1. ZIP entpacken
2. `bash scripts/bootstrap_local.sh`
3. `secrets/.env` pflegen
4. lokal testen
5. nach GitHub pushen

## Hinweis zu Tennis und EuroLeague
Diese beiden Module sind absichtlich als **hybride, rating-ready Baselines** umgesetzt:
- sie funktionieren bereits mit Live-Odds, Tracking, Risk, Calibration und CLV-Snapshots
- sie unterstützen optionale lokale Ratings/Model-Dateien
- es gibt aber noch keinen vollautomatischen historischen Datenimport für tiefes Retraining wie bei den etablierten Football/NBA/NFL-Pfaden

## Player Props
Die Props-Schiene ist jetzt für **NBA, NFL und Fußball** drin. Sie nutzt einen kombinierten Ansatz aus:
- Buchmacher-Konsens ohne Vig
- optionalen lokalen Player-Priors (`*/models/player_props_priors.json`)
- bestehendem Tracking, Risk, Calibration und Closing-Line-Snapshotting

Wichtig: Welche Prop-Märkte tatsächlich laufen, hängt von der Marktverfügbarkeit der API/Buchmacher pro Spiel ab. Fehlt ein Markt oder sind keine Over/Under-Paare vorhanden, wird dafür kein Bet erzeugt.


## Zentrale Pipelines
- `python -m shared.pipeline_runner daily`
- `python -m shared.pipeline_runner weekly`
- `python -m shared.pipeline_runner uefa`
- `python -m shared.pipeline_runner props`
- `python -m shared.pipeline_runner full`
- `bash scripts/run_daily_pipeline.sh`
- `bash scripts/run_weekly_pipeline.sh`

## Team-Settlement
- `python shared/settle_team_bets.py --help`
- `python shared/settle_team_bets.py --sport football`
- `python shared/settle_team_bets.py --sport football --leagues UCL UEL UECL`
- `python shared/settle_team_bets.py --sport euroleague --manual-only`
- `python shared/settle_team_bets.py --sport tennis --manual-only`

Manuelle Result-Dateien können unter `data/settlement/manual/*_team_results.json` abgelegt werden.


## OpenClaw Telegram Control

Der Bot kann nicht nur Alerts posten, sondern auch zentrale Jobs aus deinem Telegram-Chat starten.

### Voraussetzungen
- `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` in `secrets/.env`
- optional `TELEGRAM_ALLOWED_USER_IDS`, damit nur deine Accounts Befehle ausführen dürfen

### Starten
```bash
python -m shared.telegram_control_bot
```

oder

```bash
bash scripts/run_telegram_control_bot.sh
```

### Befehle im Chat
- `/status`
- `/daily`
- `/weekly`
- `/uefa`
- `/props`
- `/full`
- `/pipeline daily`
- `/settleteam football`
- `/settleprops all`
- `/report all 30`
- `/performance football 30`
- `/jobs 5`
- `/history 5`
- `/models all`
- `/activate_model football football-my-best-model`
- `/lastbets 5`
- `/stop`
- `/dashboard`
- `/tail`

`/performance` liefert eine schnelle Performance-Zusammenfassung direkt im Chat, ohne einen längeren Report-Job zu starten. `/jobs` zeigt den aktiven Job plus die letzten Läufe. `/history` gibt dir die letzten Pipelines und Modell-Aktivierungen. `/models` fasst aktive und neueste Kandidatenmodelle je Sport zusammen. `/activate_model` setzt einen vorhandenen Kandidaten direkt live. `/pipeline` startet jedes vorhandene Pipeline-Preset flexibel aus dem Chat. `/lastbets` zeigt die zuletzt aktiven und zuletzt abgerechneten Bets. `/stop` beendet den aktuell laufenden Pipeline- oder Settlement-Job kontrolliert.

Der Bot erlaubt immer nur **einen laufenden Job gleichzeitig** und schreibt Logs nach `data/telegram_control/logs/`.

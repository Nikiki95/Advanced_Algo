# Implemented Changes V4 — Player Props for Known Sports

Diese Stufe ergänzt **Player Props nur für die bekannten Sportarten**:
- Football / Soccer
- NBA
- NFL

## Neu
- `shared/player_props.py`: gemeinsame Prop-Analyse (No-Vig-Konsens, Priors, Kelly, Confidence)
- `shared/prop_api.py`: generische Event-Props-API-Helfer für The Odds API
- `shared/prop_settlement.py`: einfache Settlement-Helfer für Over/Under-Props
- `nba/src/player_props_scraper.py`
- `nfl/src/player_props_scraper.py`
- `football/src/scraper/player_props_scraper.py`
- `nba/cron_props.py`
- `nfl/cron_props.py`
- `football/cron_props.py`

## Tracking / Risk
- Tracker speichert jetzt optional `player_name`, `prop_side` und `metadata`
- Risk-Layer begrenzt zusätzlich die Exposition auf denselben Spieler

## Lokale Player-Priors
Für NBA, NFL und Football wurden Beispiel-Dateien ergänzt:
- `nba/models/player_props_priors.sample.json`
- `nfl/models/player_props_priors.sample.json`
- `football/models/player_props_priors.sample.json`

Beim lokalen Bootstrap werden daraus automatisch `player_props_priors.json` erzeugt, falls noch keine eigenen Dateien vorhanden sind.

## Absichtliche Grenzen
- Fokus auf **Over/Under-Props**
- keine Same Game Parlays
- keine vollautomatische Boxscore-basierte Settlement-Pipeline
- keine Player Props für Tennis / EuroLeague in dieser Stufe

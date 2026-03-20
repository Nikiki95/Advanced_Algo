# Implemented Changes V5 — Prop Settlement Pipeline

Diese Stufe schließt den Lern- und Tracking-Kreis für Player Props.

## Neu
- `shared/prop_settlement.py`: vollständige Settlement-Pipeline
- `shared/settle_player_props.py`: gemeinsamer CLI-Entry-Point
- `football/settle_props.py`
- `nba/settle_props.py`
- `nfl/settle_props.py`
- `shared/manual_settlement_samples/*.sample.json`

## Pipeline-Ablauf
- liest offene Prop-Bets aus dem Universal Tracker
- wartet standardmäßig bis einige Stunden nach Spielstart
- löst Stats erst aus manuellen Runtime-Dateien auf
- nutzt optional API-Sports als automatische Quelle
- settled Win/Loss/Push/Void
- speichert `actual_stat_value`, `settlement_source`, `settlement_event_reference` und Hinweise in den Tracker-Metadaten
- schreibt ungelöste Fälle in `data/settlement/unresolved/*.jsonl`

## Zusätzliche Fixes
- Closing-Line-Lookup vergleicht jetzt Teams, Märkte und Selections case-insensitiv
- dadurch funktionieren Prop-Closing-Lines robuster trotz unterschiedlicher Schreibweise (`Over` vs `over`)

## Setup
- `.env.example` enthält jetzt optional `APISPORTS_KEY`
- `scripts/bootstrap_local.sh` legt Runtime-Ordner für Settlement an und kopiert Beispiel-Dateien

## Hinweise
- API-Sports ist optional; ohne Key funktioniert die Pipeline weiterhin über manuelle Settlement-Dateien
- die API-Auflösung ist bewusst fehlertolerant implementiert und priorisiert Datenintegrität vor aggressivem Auto-Matching

# Implemented Changes — Known Sports Scope Refresh

## Scope-Anpassung
- Championship / `E1` aus dem aktiven Scope entfernt
- 2. Bundesliga explizit im Scope gehalten
- UEFA Europa League und Conference League als eigene Live-Schiene ergänzt
- EuroLeague als eigenes Basketball-Modul ergänzt
- Tennis als turnierbasierte H2H-Schiene ergänzt
- Player Props weiterhin bewusst **nicht** umgesetzt

## Neue Entry Points
- `football/uefa_live.py`
- `euroleague/cron_live.py`
- `tennis/cron_live.py`

## Repo / CI
- Bootstrap-Script erweitert
- CI und Smoke-Workflow um neue Module ergänzt
- README auf den neuen Scope umgestellt

- Primeira Liga / `P1` und Eredivisie / `N1` im aktiven Football-Live-Runner ergänzt

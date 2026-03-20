# Implemented Changes V6 — UEFA + Pipeline + Team Settlement

## New in V6
- Champions League (`UCL`) added to the active UEFA scope
- UEFA football result settlement now supports `UCL`, `UEL`, `UECL` with API-Sports fallback
- central pipeline runner with presets: `daily`, `weekly`, `uefa`, `props`, `full`
- generic non-prop team settlement CLI via `shared/settle_team_bets.py`
- manual team-result stores for football, NBA, NFL, EuroLeague and tennis
- simple retraining wrappers for EuroLeague and tennis
- stronger player/team matching helper reused by prop settlement
- monitoring dashboard extended with league-level performance table

## New files
- `shared/pipeline_presets.py`
- `shared/pipeline_runner.py`
- `shared/player_name_matcher.py`
- `shared/settle_team_bets.py`
- `euroleague/retrain_model.py`
- `tennis/retrain_model.py`
- `scripts/run_daily_pipeline.sh`
- `scripts/run_weekly_pipeline.sh`
- `shared/manual_settlement_samples/*_team_results.sample.json`

## Updated files
- `football/config.py`
- `football/uefa_live.py`
- `football/cron_props.py`
- `football/src/scraper/player_props_scraper.py`
- `football/src/utils/result_fetcher.py`
- `shared/config.py`
- `shared/feedback_loop.py`
- `shared/monitoring_dashboard.py`
- `shared/prop_settlement.py`
- `shared/retrain_orchestrator.py`
- `scripts/bootstrap_local.sh`
- `README.md`
- `.env.example`
- `.github/workflows/ci.yml`
- `.github/workflows/manual-smoke.yml`

## Notes
- Football UEFA team-bet settlement is automatic when API-Sports is configured; domestic football still uses football-data.co.uk first and falls back to API-Sports when needed.
- EuroLeague and tennis team settlement are supported through the generic team-settlement CLI with manual result files.
- The central pipeline standardizes the improvement loop, but it still needs Cron / a scheduler to run continuously.

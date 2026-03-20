# Implemented Changes V7.2

## Telegram Admin View Additions
- Added `/jobs [n]` to show the current running job and recent job history directly in Telegram.
- Added `/history [n]` to summarize recent pipeline runs and recent model activations.
- Added `/models [sport]` to show active models and latest candidates per sport from the model registry.
- Updated Telegram help text and README command list for the new admin commands.

## Notes
- `/jobs` reads from `data/telegram_control/current_job.json` and `job_history.jsonl`.
- `/history` summarizes pipeline run metadata from `data/pipeline_runs/*.json` plus registry activation history.
- `/models` supports `all`, `football`, `nba`, `nfl`, `euroleague`, and `tennis`.

# Implemented Changes V7.1

## Telegram Control Additions
- Added `/stop` to terminate the currently running pipeline or settlement job.
- Added `/lastbets [n]` to show recent active and recently settled bets directly in Telegram.
- Added `/performance [sport] [days]` for a fast in-chat performance summary without launching a long report job.
- Improved Telegram help text and README command list.

## Notes
- `/stop` respects the single-job lock and updates job history/status to `stopped`.
- `/lastbets` is capped at 10 entries per section to keep Telegram replies readable.
- `/performance` supports `all`, `football`, `nba`, `nfl`, `euroleague`, and `tennis`.

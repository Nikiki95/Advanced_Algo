# Implemented Changes V7

## Telegram Control Layer
- Added `shared/telegram_control_bot.py` as a long-polling Telegram command bot
- OpenClaw chat can now trigger daily, weekly, UEFA, props and full pipelines
- Added `/settleteam`, `/settleprops`, `/report`, `/dashboard`, `/tail`, `/status`, `/ping`
- V7.1 extends Telegram control with `/stop`, `/lastbets`, and `/performance`
- Added optional access control through `TELEGRAM_ALLOWED_USER_IDS`
- Added single-job lock behavior and per-job logs in `data/telegram_control/logs/`

## Supporting Changes
- `shared/telegram_bot.py` now supports plain-text sending without Markdown
- Added `scripts/run_telegram_control_bot.sh`
- Extended bootstrap for telegram control state/log directories
- Added env settings for command bot polling and runtime limits
- CI smoke checks include telegram control bot entry point

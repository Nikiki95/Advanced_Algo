# OpenClaw Setup To-Do

This file is a step-by-step working checklist for OpenClaw.

## How OpenClaw should use this file

1. Work through the sections **in order**.
2. Ask the user **only the first unanswered question** in the current section.
3. Wait for the user's answer before moving on.
4. After each completed item, mark it mentally as done and continue to the next unchecked item.
5. Do **not** ask for everything at once.
6. Prefer small batches of work: one question, then one action, then a short status update.
7. Never commit or print secrets into Git.
8. Treat `EXECUTION_MODE=shadow` as the safe default until the user explicitly wants live execution.

---

## Goal

Bring this repo into a usable state for the user with:
- environment prepared
- API keys configured
- models trained
- smoke tests passed
- Telegram / OpenClaw control bot running
- daily operation path defined

---

## Section 1 - Confirm environment

### Ask these questions, one by one
- [ ] What machine will this run on first: local PC, server, VPS, or Raspberry Pi?
- [ ] Which OS is it running on?
- [ ] Which Python version is available?
- [ ] Should the first run stay in `shadow` mode?

### Actions after answers are known
- [ ] Confirm a Python virtual environment can be created.
- [ ] Confirm the repo has been unzipped.
- [ ] Confirm the user is in the repo root.

### Suggested commands
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/bootstrap_local.sh
```

### Optional but recommended
```bash
playwright install chromium
```

---

## Section 2 - Collect required secrets and IDs

### Required keys
OpenClaw must ask for these one at a time:
- [ ] `THEODDS_API_KEY`
- [ ] `TELEGRAM_BOT_TOKEN`
- [ ] `TELEGRAM_CHAT_ID`

### Strongly recommended
- [ ] `APISPORTS_KEY`

### Optional, depending on Telegram control setup
- [ ] `TELEGRAM_ALLOWED_USER_IDS`
- [ ] `TELEGRAM_POLL_INTERVAL`
- [ ] `TELEGRAM_MAX_RUNTIME_MINUTES`

### Questions OpenClaw should ask
- [ ] Do you already have a The Odds API key?
- [ ] Do you already have an API-Sports key?
- [ ] Do you already have a Telegram bot token from BotFather?
- [ ] Do you know the Telegram chat ID for your OpenClaw chat/group?
- [ ] Do you want to restrict command access to specific Telegram user IDs?

### Actions
- [ ] Create `secrets/.env` if missing.
- [ ] Copy from `.env.example` if needed.
- [ ] Fill the known values.
- [ ] Set `EXECUTION_MODE=shadow` unless the user explicitly says otherwise.
- [ ] Set `PLAYER_PROPS_ENABLED=true` unless the user explicitly wants props disabled.

### Minimum `.env` shape
```env
THEODDS_API_KEY=
APISPORTS_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_COMMANDS_ENABLED=true
TELEGRAM_ALLOWED_USER_IDS=
TELEGRAM_POLL_INTERVAL=3
TELEGRAM_MAX_RUNTIME_MINUTES=120
EXECUTION_MODE=shadow
PLAYER_PROPS_ENABLED=true
```

---

## Section 3 - Things OpenClaw cannot do alone

These must be kept visible to the user.

- [ ] Create external accounts for APIs
- [ ] Purchase paid plans or check billing status
- [ ] Generate the actual secret keys
- [ ] Add the Telegram bot to the user's private chat or group
- [ ] Discover private Telegram IDs without the user's help
- [ ] Guarantee public third-party sites keep the same structure forever
- [ ] Decide the user's real bankroll / live staking policy
- [ ] Run a permanent 24/7 scheduler unless the user provides the host environment

If one of these blocks progress, OpenClaw should stop and ask the user only for that missing piece.

---

## Section 4 - Train core models

### Priority order
1. Football
2. NBA
3. NFL

### Questions OpenClaw should ask before training
- [ ] Do you want to train all three core sports now?
- [ ] Are network access and APIs available on this machine?

### Commands
```bash
python football/train_all_leagues.py
python nba/retrain_model.py
python nfl/retrain_model.py
```

### What OpenClaw should verify afterwards
- [ ] Football league model files exist under `football/models/leagues/`
- [ ] NBA model artifact exists
- [ ] NFL model artifact exists
- [ ] No obvious training failure was reported

### Important note
If training fails, OpenClaw should report:
- command used
- exact error
- whether it looks like a missing key, missing dependency, or upstream data source problem

---

## Section 5 - Optional model strengthening

### EuroLeague
- [ ] Ask whether EuroLeague should be refined now or later.
- [ ] If yes, run:
```bash
python euroleague/retrain_model.py
```

### Tennis
- [ ] Ask whether Tennis should be refined now or later.
- [ ] If yes, run:
```bash
python tennis/retrain_model.py
```

### Player props priors
OpenClaw should remind the user that the sample priors are only a start.

Files to review later:
- [ ] `football/models/player_props_priors.json`
- [ ] `nba/models/player_props_priors.json`
- [ ] `nfl/models/player_props_priors.json`

---

## Section 6 - Smoke tests

### Commands to test
```bash
python football/cron_live.py --help
python football/uefa_live.py --help
python nba/cron_live.py --help
python nfl/cron_live.py --help
python euroleague/cron_live.py --help
python tennis/cron_live.py --help
python football/cron_props.py --help
python nba/cron_props.py --help
python nfl/cron_props.py --help
python shared/settle_team_bets.py --help
python shared/settle_player_props.py --help
python -m shared.pipeline_runner daily
```

### OpenClaw should confirm
- [ ] each command starts cleanly
- [ ] no missing module errors
- [ ] no missing env errors beyond keys the user has not supplied yet

---

## Section 7 - Telegram / OpenClaw control

### Questions OpenClaw should ask
- [ ] Do you want to run the Telegram control bot now?
- [ ] Is the Telegram bot already in your OpenClaw chat/group?

### Start commands
```bash
python -m shared.telegram_control_bot
```

or

```bash
bash scripts/run_telegram_control_bot.sh
```

### OpenClaw should then test these commands in Telegram
- [ ] `/ping`
- [ ] `/status`
- [ ] `/jobs 5`
- [ ] `/models all`
- [ ] `/performance all 30`

If one fails, OpenClaw should identify whether the problem is:
- missing Telegram token
- wrong chat ID
- bot not added to the chat
- command access restricted by allowed user IDs

---

## Section 8 - First safe operating run

### Default safe run
OpenClaw should strongly prefer this first:
```bash
python -m shared.pipeline_runner daily
```

### Expectations
- [ ] run in `shadow` mode
- [ ] collect odds and candidate bets
- [ ] create logs / tracked bet records
- [ ] do not assume live staking until user explicitly approves it

---

## Section 9 - Decide how continuous operation will work

### OpenClaw should ask
- [ ] Do you want to operate this manually, via Telegram commands, via cron, or as a permanent service?
- [ ] Should daily and weekly pipelines be scheduled automatically?

### Options
- [ ] manual only
- [ ] Telegram-driven
- [ ] cron
- [ ] systemd service
- [ ] Docker / VPS setup

### Important
OpenClaw should remind the user that the system improves continuously only if runs, settlements, and retraining are actually scheduled or triggered.

---

## Section 10 - APIs and external dependencies to keep in mind

### Required
- [ ] The Odds API (`THEODDS_API_KEY`)

### Strongly recommended
- [ ] API-Sports (`APISPORTS_KEY`)

### Required for Telegram control
- [ ] Telegram Bot API (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)

### Public / external data sources used in parts of the repo
These may break or change over time and are not under local control.
- [ ] football-data.co.uk
- [ ] fixturedownload.com
- [ ] Understat
- [ ] ESPN
- [ ] Basketball Reference
- [ ] Reddit
- [ ] SBR
- [ ] Transfermarkt

---

## Section 11 - Done criteria

OpenClaw should only say the repo is operational when all of these are true:
- [ ] virtual environment works
- [ ] dependencies installed
- [ ] `secrets/.env` configured
- [ ] required API keys present
- [ ] football models trained
- [ ] nba model trained
- [ ] nfl model trained
- [ ] smoke tests pass
- [ ] Telegram control bot responds
- [ ] first pipeline run completed in shadow mode
- [ ] user has chosen an operating mode for continuous use

---

## Short version OpenClaw can follow immediately

1. Ask where the repo will run.
2. Ask for The Odds API key.
3. Ask for Telegram bot token and Telegram chat ID.
4. Ask whether API-Sports is available.
5. Prepare `.env`.
6. Create venv, install requirements, run bootstrap.
7. Train football, nba, nfl models.
8. Run smoke tests.
9. Start Telegram control bot.
10. Run the first daily pipeline in shadow mode.
11. Ask how the user wants continuous operation handled.


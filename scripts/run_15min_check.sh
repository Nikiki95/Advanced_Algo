#!/bin/bash
# 15-Minute Value Check - ON DEMAND (nicht automatisch)
# Manuell starten mit: bash scripts/run_15min_check.sh

LOG_DIR="~/.openclaw/workspace/betting-algorithm/logs"
mkdir -p "$LOG_DIR"

echo "🏃 15-Minute Check gestartet: $(date)"

cd ~/.openclaw/workspace/betting-algorithm
source .venv/bin/activate
export $(grep -v '^#' secrets/.env | xargs)

# Football quick check
echo "⚽ Checking Football..."
timeout 120 python football/cron_live.py --shadow --leagues D1 E0 >> "$LOG_DIR/15min_football.log" 2>&1

# NBA quick check
echo "🏀 Checking NBA..."
timeout 120 python nba/cron_live.py --shadow >> "$LOG_DIR/15min_nba.log" 2>&1

# NFL (if in season - will return 0 games otherwise)
echo "🏈 Checking NFL..."
timeout 60 python nfl/cron_live.py --shadow >> "$LOG_DIR/15min_nfl.log" 2>&1

echo "✅ 15-Minute Check abgeschlossen: $(date)"

#!/bin/bash
# Setup 15-minute NBA Value Check Cron

echo "Setting up 15-minute NBA Value Check Cron..."

# Create the cron entry
CRON_ENTRY="*/15 * * * * cd $(pwd) && ./nba/venv/bin/python nba/cron_live.py >> nba/logs/cron_$(date +\%Y\%m\%d).log 2>&1"

# Remove existing entry if exists
(crontab -l 2>/dev/null | grep -v "nba/cron_live.py") | crontab -

# Add new entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job installed:"
echo "   Runs every: 15 minutes"
echo "   Script: nba/cron_live.py"
echo "   Logs: nba/logs/cron_YYYYMMDD.log"
echo ""
crontab -l | tail -3

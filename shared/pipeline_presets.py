"""Named command presets for recurring pipeline runs."""
from __future__ import annotations

import sys

PY = sys.executable

PIPELINE_PRESETS = {
    'daily': [
        # NFL PAUSED until September 2026 (Off-Season)
        [PY, 'football/cron_live.py'],
        [PY, 'football/uefa_live.py'],
        [PY, 'nba/cron_live.py'],
        # [PY, 'nfl/cron_live.py'],  # PAUSED - Off-Season
        [PY, 'euroleague/cron_live.py'],
        [PY, 'tennis/cron_live.py'],
        [PY, 'shared/settle_team_bets.py', '--sport', 'football'],
        [PY, 'shared/settle_team_bets.py', '--sport', 'euroleague', '--manual-only'],
        [PY, 'shared/settle_team_bets.py', '--sport', 'tennis', '--manual-only'],
        [PY, 'shared/settle_player_props.py', '--sport', 'all'],
        [PY, '-m', 'shared.feedback_loop', '--sport', 'all', '--days', '60', '--generate-dashboard'],
    ],
    'weekly': [
        [PY, '-m', 'shared.feedback_loop', '--sport', 'all', '--days', '90', '--generate-calibration', '--optimize-thresholds', '--generate-dashboard'],
        [PY, '-m', 'shared.retrain_orchestrator', '--sport', 'all'],
    ],
    'uefa': [
        [PY, 'football/uefa_live.py', '--competitions', 'UCL', 'UEL', 'UECL'],
        [PY, 'shared/settle_team_bets.py', '--sport', 'football', '--leagues', 'UCL', 'UEL', 'UECL'],
        [PY, 'football/cron_props.py', '--scopes', 'UCL', 'UEL', 'UECL'],
        [PY, 'football/settle_props.py'],
    ],
    'props': [
        [PY, 'football/cron_props.py'],
        [PY, 'nba/cron_props.py'],
        # [PY, 'nfl/cron_props.py'],  # PAUSED - Off-Season
        [PY, 'shared/settle_player_props.py', '--sport', 'all'],
    ],
}

PIPELINE_PRESETS['full'] = PIPELINE_PRESETS['daily'] + PIPELINE_PRESETS['weekly']

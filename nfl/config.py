"""NFL configuration wrapper."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import nfl_config as cfg

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"
for d in [DATA_DIR, MODELS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

THEODDS_API_KEY = cfg.THEODDS_API_KEY or os.getenv("THEODDS_API_KEY", "")
TELEGRAM_BOT_TOKEN = cfg.TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = cfg.TELEGRAM_CHAT_ID or os.getenv("TELEGRAM_CHAT_ID", "")

THEODDS_BASE_URL = cfg.THEODDS_BASE_URL
NFL_SPORT_KEY = cfg.SPORT_KEY
ODDS_MARKETS = cfg.ODDS_MARKETS
REGIONS = cfg.ODDS_REGIONS
ODDS_FORMAT = cfg.ODDS_FORMAT

NFL_CONFIG = {"name": "NFL", "season": cfg.SEASON, "num_teams": 32, "games_per_season": 17, "playoff_teams": 14}
POWER_RANK_CONFIG = {"initial_rating": 0, "home_field_advantage": cfg.HOME_FIELD_ADVANTAGE, "inter_season_regression": cfg.INTER_SEASON_REGRESSION, "learning_rate": cfg.LEARNING_RATE, "spread_std_dev": cfg.SPREAD_STD_DEV, "training_weeks": cfg.TRAINING_WEEKS}
VALUE_THRESHOLDS = {"moneyline": cfg.MONEYLINE_THRESHOLD, "spread": cfg.SPREAD_THRESHOLD, "totals": cfg.TOTALS_THRESHOLD}
KELLY_CONFIG = {"fraction": cfg.KELLY_FRACTION, "max_bet_percent": cfg.MAX_BET_PERCENT, "min_odds": cfg.MIN_ODDS, "max_odds": cfg.MAX_ODDS}
FEATURES = {"rest_days": True, "home_field": True, "qb_rating": False, "injury_adjustment": False}
LOG_LEVEL = "INFO"
SCHEDULE_CONFIG = {"check_interval_hours": 6, "odds_update_before_hours": 12}

PLAYER_PROP_MARKETS = ['player_pass_yds', 'player_pass_tds', 'player_rush_yds', 'player_reception_yds', 'player_receptions']
PLAYER_PROP_VALUE_THRESHOLD = 0.05
PLAYER_PROP_KELLY_FRACTION = 0.12
PLAYER_PROP_MAX_BET_PERCENT = 0.012
PLAYER_PROP_PRIOR_WEIGHT = 0.30

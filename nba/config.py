"""NBA configuration wrapper."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import nba_config as cfg

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
NBA_SPORT_KEY = cfg.SPORT_KEY
ODDS_MARKETS = cfg.ODDS_MARKETS
REGIONS = cfg.ODDS_REGIONS
ODDS_FORMAT = cfg.ODDS_FORMAT

ELO_CONFIG = {
    "initial_elo": cfg.ELO_INITIAL,
    "k_factor": cfg.ELO_K_FACTOR,
    "home_advantage": cfg.ELO_HOME_ADVANTAGE,
    "margin_of_victory_mult": cfg.ELO_MARGIN_MULT,
    "season_regression": cfg.ELO_SEASON_REGRESSION,
    "min_games_for_reliable": cfg.ELO_MIN_GAMES_RELIABLE,
    "training_games": cfg.ELO_TRAINING_GAMES,
}

NBA_CONFIG = {"name": "NBA", "season": cfg.SEASON, "num_teams": 30, "games_per_season": 82, "playoff_teams": 16}
VALUE_THRESHOLDS = {"moneyline": cfg.MONEYLINE_THRESHOLD, "spread": cfg.SPREAD_THRESHOLD, "totals": cfg.TOTALS_THRESHOLD}
KELLY_CONFIG = {"fraction": cfg.KELLY_FRACTION, "max_bet_percent": cfg.MAX_BET_PERCENT, "min_odds": cfg.MIN_ODDS, "max_odds": cfg.MAX_ODDS}
FEATURES = {"back_to_back": cfg.FEATURE_BACK_TO_BACK, "rest_days": cfg.FEATURE_REST_DAYS, "injury_adjustment": cfg.FEATURE_INJURY_ADJUSTMENT}
LOG_LEVEL = "INFO"

PLAYER_PROP_MARKETS = ['player_points', 'player_rebounds', 'player_assists', 'player_threes']
PLAYER_PROP_VALUE_THRESHOLD = 0.045
PLAYER_PROP_KELLY_FRACTION = 0.15
PLAYER_PROP_MAX_BET_PERCENT = 0.015
PLAYER_PROP_PRIOR_WEIGHT = 0.30

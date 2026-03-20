"""EuroLeague configuration."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import euroleague_config

SPORT_KEY = euroleague_config.SPORT_KEY
REGIONS = euroleague_config.ODDS_REGIONS
THEODDS_API_KEY = euroleague_config.THEODDS_API_KEY
THEODDS_BASE_URL = euroleague_config.THEODDS_BASE_URL
MODELS_DIR = euroleague_config.models_dir
DATA_DIR = euroleague_config.data_dir
HOME_ADVANTAGE_ELO = euroleague_config.HOME_ADVANTAGE_ELO

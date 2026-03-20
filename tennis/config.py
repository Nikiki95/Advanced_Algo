"""Tennis configuration."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import tennis_config

TOURNAMENTS = tennis_config.SUPPORTED_TOURNAMENTS
REGIONS = tennis_config.ODDS_REGIONS
THEODDS_API_KEY = tennis_config.THEODDS_API_KEY
THEODDS_BASE_URL = tennis_config.THEODDS_BASE_URL
MODELS_DIR = tennis_config.models_dir
DATA_DIR = tennis_config.data_dir

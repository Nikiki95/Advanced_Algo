"""Football configuration wrapper."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import football_config

config = football_config

LEAGUE_MAPPING = {
    "D1": {"name": "Bundesliga", "football_data_code": "D1", "country": "Germany"},
    "D2": {"name": "2. Bundesliga", "football_data_code": "D2", "country": "Germany"},
    "E0": {"name": "Premier League", "football_data_code": "E0", "country": "England"},
    "SP1": {"name": "La Liga", "football_data_code": "SP1", "country": "Spain"},
    "I1": {"name": "Serie A", "football_data_code": "I1", "country": "Italy"},
    "F1": {"name": "Ligue 1", "football_data_code": "F1", "country": "France"},
    "P1": {"name": "Primeira Liga", "football_data_code": "P1", "country": "Portugal"},
    "N1": {"name": "Eredivisie", "football_data_code": "N1", "country": "Netherlands"},
}

UEFA_COMPETITIONS = {
    "UCL": {"name": "Champions League", "sport_key": "soccer_uefa_champs_league"},
    "UEL": {"name": "Europa League", "sport_key": "soccer_uefa_europa_league"},
    "UECL": {"name": "Conference League", "sport_key": "soccer_uefa_europa_conference_league"},
}

TARGET_BOOKMAKERS = ["bet365", "pinnacle", "betfair", "williamhill"]

PLAYER_PROP_MARKETS = ['player_shots', 'player_shots_on_target', 'player_assists_soccer', 'player_passes', 'player_tackles', 'player_cards']
PLAYER_PROP_VALUE_THRESHOLD = 0.05
PLAYER_PROP_KELLY_FRACTION = 0.10
PLAYER_PROP_MAX_BET_PERCENT = 0.010
PLAYER_PROP_PRIOR_WEIGHT = 0.22

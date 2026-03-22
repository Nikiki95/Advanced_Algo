"""
Unified Configuration for Betting Algorithm Suite
All sports share one Pydantic-based config.
"""
from pydantic import Field
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List, Dict


class SharedConfig(BaseSettings):
    """Gemeinsame Konfiguration aus .env"""

    THEODDS_API_KEY: str = Field(default="", description="TheOddsAPI Key")
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot Token")
    APISPORTS_KEY: str = Field(default="", description="API-Sports Key")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Telegram Chat ID")

    THEODDS_BASE_URL: str = "https://api.the-odds-api.com/v4"
    ODDS_FORMAT: str = "decimal"
    BASE_DIR: Path = Field(default=Path(__file__).parent.parent)
    DEFAULT_BANKROLL: float = Field(default=1000.0, description="Default bankroll in EUR")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def secrets_env(self) -> Path:
        return self.BASE_DIR / "secrets" / ".env"


class FootballConfig(SharedConfig):
    MIN_VALUE_THRESHOLD: float = 0.02
    KELLY_FRACTION: float = 0.25
    DC_RHO: float = -0.13
    DC_DECAY: float = 0.0035
    TRAINING_YEARS: int = 3
    LEAGUES: List[str] = ["D1", "D2"]
    OU_VALUE_THRESHOLD: float = 0.04
    OU_DEFAULT_LINE: float = 2.5
    OU_MAX_GOALS: int = 7
    DC_VALUE_THRESHOLD: float = 0.03
    ODDS_UPDATE_INTERVAL_MIN: int = 30
    ODDS_REGIONS: str = "eu"
    SPORT_KEYS: Dict[str, str] = {
        "bundesliga": "soccer_germany_bundesliga",
        "2bundesliga": "soccer_germany_bundesliga_2",
        "epl": "soccer_epl",
        "laliga": "soccer_spain_la_liga",
        "seriea": "soccer_italy_serie_a",
        "ligue1": "soccer_france_ligue_one",
        "primeira": "soccer_portugal_primeira_liga",
        "eredivisie": "soccer_netherlands_eredivisie",
        "champions": "soccer_uefa_champs_league",
        "europa": "soccer_uefa_europa_league",
        "conference": "soccer_uefa_europa_conference_league",
    }

    @property
    def data_dir(self) -> Path:
        return self.BASE_DIR / "football" / "data"

    @property
    def models_dir(self) -> Path:
        return self.BASE_DIR / "football" / "models"


class NBAConfig(SharedConfig):
    SPORT_KEY: str = "basketball_nba"
    ODDS_MARKETS: List[str] = ["h2h", "spreads", "totals"]
    ODDS_REGIONS: str = "eu"
    SEASON: str = "2025-26"
    ELO_INITIAL: float = 1500.0
    ELO_K_FACTOR: float = 20.0
    ELO_HOME_ADVANTAGE: float = 100.0
    ELO_MARGIN_MULT: float = 1.0
    ELO_SEASON_REGRESSION: float = 0.25
    ELO_MIN_GAMES_RELIABLE: int = 10
    ELO_TRAINING_GAMES: int = 150
    MONEYLINE_THRESHOLD: float = 0.05
    SPREAD_THRESHOLD: float = 0.03
    TOTALS_THRESHOLD: float = 0.04
    KELLY_FRACTION: float = 0.25
    MAX_BET_PERCENT: float = 5.0
    MIN_ODDS: float = 1.30
    MAX_ODDS: float = 10.0
    AVG_PACE: float = 100.0
    AVG_ORTG: float = 112.0
    TOTALS_STD_DEV: float = 12.0
    FEATURE_BACK_TO_BACK: bool = True
    FEATURE_REST_DAYS: bool = True
    FEATURE_INJURY_ADJUSTMENT: bool = True

    @property
    def data_dir(self) -> Path:
        return self.BASE_DIR / "nba" / "data"

    @property
    def models_dir(self) -> Path:
        return self.BASE_DIR / "nba" / "models"


class EuroleagueConfig(SharedConfig):
    SPORT_KEY: str = "basketball_euroleague"
    ODDS_MARKETS: List[str] = ["h2h", "spreads", "totals"]
    ODDS_REGIONS: str = "eu"
    MONEYLINE_THRESHOLD: float = 0.045
    SPREAD_THRESHOLD: float = 0.03
    TOTALS_THRESHOLD: float = 0.035
    KELLY_FRACTION: float = 0.20
    HOME_ADVANTAGE_ELO: float = 70.0

    @property
    def data_dir(self) -> Path:
        return self.BASE_DIR / "euroleague" / "data"

    @property
    def models_dir(self) -> Path:
        return self.BASE_DIR / "euroleague" / "models"


class NFLConfig(SharedConfig):
    SPORT_KEY: str = "americanfootball_nfl"
    ODDS_MARKETS: List[str] = ["h2h", "spreads", "totals"]
    ODDS_REGIONS: str = "us"
    SEASON: str = "2025-26"
    HOME_FIELD_ADVANTAGE: float = 2.5
    INTER_SEASON_REGRESSION: float = 0.30
    LEARNING_RATE: float = 0.30
    SPREAD_STD_DEV: float = 12.0
    TRAINING_WEEKS: int = 17
    MONEYLINE_THRESHOLD: float = 0.06
    SPREAD_THRESHOLD: float = 0.04
    TOTALS_THRESHOLD: float = 0.05
    KELLY_FRACTION: float = 0.25
    MAX_BET_PERCENT: float = 4.0
    MIN_ODDS: float = 1.25
    MAX_ODDS: float = 8.0

    @property
    def data_dir(self) -> Path:
        return self.BASE_DIR / "nfl" / "data"

    @property
    def models_dir(self) -> Path:
        return self.BASE_DIR / "nfl" / "models"


class TennisConfig(SharedConfig):
    ODDS_REGIONS: str = "eu"
    MARKETS: List[str] = ["h2h"]
    VALUE_THRESHOLD: float = 0.035
    KELLY_FRACTION: float = 0.15
    SUPPORTED_TOURNAMENTS: Dict[str, str] = {
        "atp_indian_wells": "tennis_atp_indian_wells",
        "atp_miami": "tennis_atp_miami_open",
        "atp_madrid": "tennis_atp_madrid_open",
        "atp_rome": "tennis_atp_italian_open",
        "atp_wimbledon": "tennis_atp_wimbledon",
        "atp_us_open": "tennis_atp_us_open",
        "wta_indian_wells": "tennis_wta_indian_wells",
        "wta_miami": "tennis_wta_miami_open",
        "wta_madrid": "tennis_wta_madrid_open",
        "wta_rome": "tennis_wta_italian_open",
        "wta_wimbledon": "tennis_wta_wimbledon",
        "wta_us_open": "tennis_wta_us_open",
    }

    @property
    def data_dir(self) -> Path:
        return self.BASE_DIR / "tennis" / "data"

    @property
    def models_dir(self) -> Path:
        return self.BASE_DIR / "tennis" / "models"


shared_config = SharedConfig()
football_config = FootballConfig()
nba_config = NBAConfig()
euroleague_config = EuroleagueConfig()
nfl_config = NFLConfig()
tennis_config = TennisConfig()

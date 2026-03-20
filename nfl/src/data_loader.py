"""
NFL Data Loader
Holt Spieldaten, Team-Stats und Ergebnisse.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NFLLoader:
    """Lädt NFL-Daten."""
    
    def __init__(self):
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def fetch_schedule(self, season: str = "2025") -> pd.DataFrame:
        """Spielplan laden."""
        logger.warning("NFL Data-Loader: Mock-Modus")
        return self._mock_schedule(season)
    
    def fetch_games(self, weeks_back: int = 8) -> pd.DataFrame:
        """Vergangene Spiele."""
        logger.info(f"Lade NFL-Spiele der letzten {weeks_back} Wochen...")
        return self._mock_games(weeks_back)
    
    def _mock_schedule(self, season: str) -> pd.DataFrame:
        """Mock Spielplan."""
        teams = [
            "KC", "SF", "BAL", "DET", "BUF", "PHI", "DAL", "MIA",
            "CIN", "CLE", "PIT", "GB", "MIN", "LAR", "SEA", "TB",
            "NO", "ATL", "CAR", "IND", "TEN", "JAX", "HOU", "DEN",
            "LAC", "LV", "NYJ", "NYG", "WAS", "CHI", "ARI", "NE"
        ]
        
        games = []
        for week in range(1, 19):  # 18 Wochen Regular Season
            for i in range(16):  # 16 Spiele pro Woche
                home = teams[i % 32]
                away = teams[(i + 1) % 32]
                games.append({
                    "game_id": f"nfl_{season}_w{week}_g{i}",
                    "week": week,
                    "date": f"2025-{9 + week // 4:02d}-{1 + (i % 7):02d}",
                    "home_team": home,
                    "away_team": away,
                    "home_score": None,
                    "away_score": None,
                    "played": False,
                })
        return pd.DataFrame(games)
    
    def _mock_games(self, weeks: int) -> pd.DataFrame:
        """Mock vergangene Spiele."""
        teams = ["KC", "SF", "BAL", "DET", "BUF", "PHI", "DAL", "MIA",
                 "CIN", "CLE", "PIT", "GB", "MIN", "LAR", "SEA", "TB"]
        
        games = []
        for week in range(weeks):
            for i in range(8):
                home = teams[i % 16]
                away = teams[(i + 4) % 16]
                h_score = 20 + (i * 3 % 25)
                a_score = 17 + (i * 7 % 22)
                games.append({
                    "game_id": f"hist_w{week}_g{i}",
                    "week": week + 1,
                    "home_team": home,
                    "away_team": away,
                    "home_score": h_score,
                    "away_score": a_score,
                    "home_win": h_score > a_score,
                    "margin": abs(h_score - a_score),
                })
        return pd.DataFrame(games)

loader = NFLLoader()

if __name__ == "__main__":
    games = loader.fetch_games(weeks_back=4)
    print(f"Geladene Spiele: {len(games)}")
    print(games.head())

"""
NBA Data Loader
Lädt Spieldaten, Team-Infos und Ergebnisse.
"""

import requests
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NBALoader:
    """Lädt NBA-Daten aus verschiedenen Quellen."""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://api.nba.com/v1"  # Offizielle NBA API
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def fetch_schedule(self, season: str = "2025-26") -> pd.DataFrame:
        """Lädt den Spielplan für eine Saison."""
        cache_file = self.cache_dir / f"schedule_{season}.pkl"
        
        if cache_file.exists():
            logger.info(f"Lade Schedule aus Cache: {cache_file}")
            return pd.read_pickle(cache_file)
        
        # TODO: NBA API Integration
        # Für jetzt: Mock-Daten für Entwicklung
        logger.warning("NBA API noch nicht verbunden - verwende Mock-Daten")
        return self._mock_schedule(season)
    
    def fetch_games(self, days_back: int = 30) -> pd.DataFrame:
        """Lägt vergangene Spiele."""
        # TODO: Implementierung
        logger.info(f"Lade Spiele der letzten {days_back} Tage...")
        return self._mock_games(days_back)
    
    def fetch_standings(self) -> pd.DataFrame:
        """Aktuelle Tabelle."""
        # TODO: Implementierung
        logger.warning("Standings noch nicht implementiert")
        return pd.DataFrame()
    
    def fetch_boxscore(self, game_id: str) -> Dict:
        """Detaillierte Spielstatistiken."""
        # TODO: Implementierung
        return {}
    
    def _mock_schedule(self, season: str) -> pd.DataFrame:
        """Temporäre Mock-Daten für Entwicklung."""
        teams = [
            "LAL", "GSW", "BOS", "MIL", "DEN", "PHX", "MIA", "PHI",
            "LAC", "DAL", "SAC", "NYK", "CLE", "NOP", "TOR"
        ]
        
        games = []
        start = datetime.now()
        
        for i in range(100):  # 100 Mock-Spiele
            home = teams[i % len(teams)]
            away = teams[(i + 1) % len(teams)]
            date = start + timedelta(days=i % 14)
            
            games.append({
                "game_id": f"mock_{i}",
                "date": date.strftime("%Y-%m-%d"),
                "home_team": home,
                "away_team": away,
                "home_score": None,
                "away_score": None,
                "season": season,
                "played": False,
            })
        
        return pd.DataFrame(games)
    
    def _mock_games(self, days_back: int) -> pd.DataFrame:
        """Mock vergangene Spiele mit Ergebnissen."""
        teams = [
            "LAL", "GSW", "BOS", "MIL", "DEN", "PHX", "MIA", "PHI",
            "LAC", "DAL", "SAC", "NYK", "CLE", "NOP", "TOR"
        ]
        
        games = []
        start = datetime.now() - timedelta(days=days_back)
        
        for i in range(days_back * 8):  # ~8 Spiele pro Tag
            home = teams[i % len(teams)]
            away = teams[(i + 3) % len(teams)]
            date = start + timedelta(days=i // 8)
            
            # Zufällige Ergebnisse
            home_score = 100 + (i * 7 % 40)
            away_score = 100 + (i * 13 % 40)
            
            games.append({
                "game_id": f"hist_{i}",
                "date": date.strftime("%Y-%m-%d"),
                "home_team": home,
                "away_team": away,
                "home_score": home_score,
                "away_score": away_score,
                "season": "2025-26",
                "played": True,
                "home_win": home_score > away_score,
                "margin": abs(home_score - away_score),
            })
        
        return pd.DataFrame(games)
    
    def cache_games(self, games: pd.DataFrame, season: str):
        """Speichert Spiele im Cache."""
        cache_file = self.cache_dir / f"games_{season}.pkl"
        games.to_pickle(cache_file)
        logger.info(f"Games cached: {cache_file}")

# Hauptinstanz
loader = NBALoader()

if __name__ == "__main__":
    # Test
    logger.info("NBA Data Loader Test")
    games = loader.fetch_games(days_back=7)
    print(f"Geladene Spiele: {len(games)}")
    print(games.head())

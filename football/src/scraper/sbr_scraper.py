"""
SportsbookReview (SBR) Scraper für Live-Odds
Nutzung von sbrscrape oder eigener Implementation als Fallback
"""
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd

from config import config, TARGET_BOOKMAKERS


@dataclass
class OddsData:
    """Strukturierte Odds-Daten"""
    event_id: str
    match_name: str
    home_team: str
    away_team: str
    league: str
    match_datetime: datetime
    
    # Odds pro Bookmaker
    odds_1: Dict[str, float]  # Heimsieg
    odds_x: Dict[str, float]  # Unentschieden
    odds_2: Dict[str, float]  # Auswärtssieg
    
    # Implied Probabilities (beste Odds)
    implied_prob_1: float
    implied_prob_x: float
    implied_prob_2: float
    
    overround: float
    timestamp: datetime


class SBRScraper:
    """
    Scraped Odds von SportsbookReview.com
    Unterstützt Bundesliga und andere europäische Top-Ligen
    """
    
    BASE_URL = "https://www.sportsbookreview.com"
    API_BASE = "https://api.sportsbookreview.com"
    
    # League IDs für SBR
    LEAGUE_IDS = {
        # Deutschland
        "bundesliga": "ger.1",
        "2-bundesliga": "ger.2",
        # England
        "premier-league": "eng.1",
        "championship": "eng.2",
        # Spanien
        "la-liga": "esp.1",
        # Italien
        "serie-a": "ita.1",
        # Frankreich
        "ligue-1": "fra.1",
        # Champions League
        "champions-league": "uefa.champions",
    }
    
    def __init__(self, use_cache: bool = True):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.use_cache = use_cache
        self.cache_dir = Path("data/cache/odds")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_upcoming_matches(self, league: str = "bundesliga", days: int = 3) -> List[OddsData]:
        """
        Holt kommende Matches mit Odds für eine Liga
        
        Args:
            league: Liga-Slug (bundesliga, premier-league, etc.)
            days: Wie viele Tage in die Zukunft
        """
        print(f"[SBR] Suche Odds für {league}...")
        
        try:
            # Versuche API-Endpunkt
            return self._fetch_via_api(league, days)
        except Exception as e:
            print(f"[SBR] API fehlgeschlagen, nutze HTML-Scraping: {e}")
            return self._fetch_via_html(league, days)
    
    def _fetch_via_api(self, league: str, days: int) -> List[OddsData]:
        """
        Nutzt die interne SBR API (Reverse-Engineered)
        """
        league_id = self.LEAGUE_IDS.get(league.lower(), league)
        
        # API-Endpunkt für Fixtures
        url = f"{self.API_BASE}/v5/fixtures/"
        
        params = {
            "league": league_id,
            "sport": "soccer",
            "limit": 50,
            "upcoming": "true"
        }
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        matches = []
        
        for fixture in data.get('fixtures', []):
            # Parse Match-Daten
            match = self._parse_fixture(fixture)
            if match:
                matches.append(match)
        
        # Hole Odds separat
        self._enrich_with_odds(matches)
        
        return matches
    
    def _parse_fixture(self, fixture: dict) -> Optional[OddsData]:
        """Parsed ein Fixture-Datenobjekt"""
        try:
            event_id = fixture.get('id', '')
            home_team = fixture.get('home', {}).get('name', '')
            away_team = fixture.get('away', {}).get('name', '')
            
            match_time = fixture.get('startTime', '')
            match_datetime = datetime.fromisoformat(match_time.replace('Z', '+00:00'))
            
            # Überspringe alte Spiele
            if match_datetime < datetime.now().replace(tzinfo=match_datetime.tzinfo):
                return None
            
            league_info = fixture.get('league', {})
            league_name = league_info.get('name', 'Unknown')
            
            return OddsData(
                event_id=event_id,
                match_name=f"{home_team} vs {away_team}",
                home_team=home_team,
                away_team=away_team,
                league=league_name,
                match_datetime=match_datetime,
                odds_1={},
                odds_x={},
                odds_2={},
                implied_prob_1=0.0,
                implied_prob_x=0.0,
                implied_prob_2=0.0,
                overround=0.0,
                timestamp=datetime.now()
            )
        except Exception as e:
            print(f"[SBR] Fehler beim Parsen: {e}")
            return None
    
    def _enrich_with_odds(self, matches: List[OddsData]):
        """Holt Odds für eine Liste von Matches"""
        event_ids = [m.event_id for m in matches]
        
        if not event_ids:
            return
        
        # Batch-Request für Odds
        url = f"{self.API_BASE}/v5/odds/"
        
        for match in matches:
            try:
                odds = self._get_match_odds(match.event_id)
                
                match.odds_1 = odds.get('1', {})
                match.odds_x = odds.get('X', {})
                match.odds_2 = odds.get('2', {})
                
                # Berechne beste Implied Probs
                match.implied_prob_1 = self._best_implied_prob(match.odds_1)
                match.implied_prob_x = self._best_implied_prob(match.odds_x)
                match.implied_prob_2 = self._best_implied_prob(match.odds_2)
                
                # Overround (Bookmaker-Marge)
                match.overround = (match.implied_prob_1 + match.implied_prob_x + match.implied_prob_2) - 1.0
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                print(f"[SBR] Odds-Fehler für {match.match_name}: {e}")
    
    def _get_match_odds(self, event_id: str) -> Dict:
        """Holt Odds für ein einzelnes Event"""
        url = f"{self.API_BASE}/v5/odds/?event={event_id}"
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        odds_by_outcome = {'1': {}, 'X': {}, '2': {}}
        
        for odds_group in data.get('odds', []):
            bookmaker = odds_group.get('bookmaker', {}).get('name', '').lower()
            
            if bookmaker not in TARGET_BOOKMAKERS:
                continue
            
            outcome = odds_group.get('outcome', {}).get('name', '')
            odds_value = odds_group.get('odds', 0)
            
            if outcome == 'Home' and odds_value > 1:
                odds_by_outcome['1'][bookmaker] = odds_value
            elif outcome == 'Draw' and odds_value > 1:
                odds_by_outcome['X'][bookmaker] = odds_value
            elif outcome == 'Away' and odds_value > 1:
                odds_by_outcome['2'][bookmaker] = odds_value
        
        return odds_by_outcome
    
    def _best_implied_prob(self, odds: Dict[str, float]) -> float:
        """Beste Implied Probability (höchste Quote)"""
        if not odds:
            return 0.0
        best_odds = max(odds.values())
        return 1.0 / best_odds
    
    def _fetch_via_html(self, league: str, days: int) -> List[OddsData]:
        """Fallback: HTML-Scraping wenn API nicht verfügbar"""
        # Vereinfachte Implementation
        # In Produktion: BeautifulSoup Parsing der SBR-Seite
        print("[SBR] HTML-Scraping aktiviert (vereinfacht)")
        return []
    
    def _normalize_team_name(self, name: str) -> str:
        """Normalisiert Team-Namen zwischen Datenquellen"""
        mappings = {
            # Bundesliga mappings
            "Bayern Munich": "Bayern Munich",
            "Bayern München": "Bayern Munich",
            "Dortmund": "Dortmund",
            "Borussia Dortmund": "Dortmund",
            "Leverkusen": "Leverkusen",
            "Bayer Leverkusen": "Leverkusen",
            "RB Leipzig": "RB Leipzig",
            "Leipzig": "RB Leipzig",
        }
        return mappings.get(name, name)


class MockSBRScraper:
    """
    Mock-Scraper für Tests ohne Netzwerkzugriff
    """
    
    def get_upcoming_matches(self, league: str = "bundesliga", days: int = 3) -> List[OddsData]:
        """Generiert Mock-Daten für Tests"""
        from datetime import datetime, timedelta
        
        mock_matches = [
            OddsData(
                event_id="mock_1",
                match_name="Bayern Munich vs Dortmund",
                home_team="Bayern Munich",
                away_team="Dortmund",
                league="Bundesliga",
                match_datetime=datetime.now() + timedelta(days=1),
                odds_1={"bet365": 1.75, "pinnacle": 1.78},
                odds_x={"bet365": 4.20, "pinnacle": 4.15},
                odds_2={"bet365": 4.50, "pinnacle": 4.40},
                implied_prob_1=0.56,
                implied_prob_x=0.24,
                implied_prob_2=0.22,
                overround=0.02,
                timestamp=datetime.now()
            ),
            OddsData(
                event_id="mock_2",
                match_name="Leverkusen vs Leipzig",
                home_team="Leverkusen",
                away_team="RB Leipzig",
                league="Bundesliga",
                match_datetime=datetime.now() + timedelta(days=1, hours=3),
                odds_1={"bet365": 2.10, "pinnacle": 2.15},
                odds_x={"bet365": 3.50, "pinnacle": 3.45},
                odds_2={"bet365": 3.40, "pinnacle": 3.35},
                implied_prob_1=0.47,
                implied_prob_x=0.29,
                implied_prob_2=0.29,
                overround=0.05,
                timestamp=datetime.now()
            )
        ]
        
        return mock_matches
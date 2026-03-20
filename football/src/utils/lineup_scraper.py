""" Football Lineup & Injury Scraper
Holt Verletzte und Aufstellungen für Football (Soccer)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from team_database import ALL_TEAMS, TEAM_LEAGUE_MAPPING

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json


class FootballLineupScraper:
    """
    Scrapt Verletzte und Aufstellungen für europäische Ligen.
    Unterstützt ALLE 96 Teams aus Top-5-Ligen!
    """
    
    # Nutze komplette Datenbank: 18 Bundesliga + 20 EPL + 20 La Liga + 20 Serie A + 18 Ligue 1
    KEY_PLAYERS = ALL_TEAMS  # 96 Teams total
    TEAM_LEAGUE = TEAM_LEAGUE_MAPPING
    
    # Position-Impact (Schlüsselpositionen)
    POSITION_IMPACT = {
        'Goalkeeper': 1.5,
        'Centre-Back': 1.3,
        'Striker': 1.2,
        'Midfield': 1.0,
        'Winger': 0.9,
    }
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("data/lineups")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_team_lineup(self, team: str, match_date: str = None) -> Dict:
        """
        Holt Aufstellung/Verletzte für ein Team.
        Unterstützt ALLE 96 Teams aus Top-5-Ligen!
        """
        # Fallback: Normalisiere Team-Namen
        normalized_team = self._normalize_team_name(team)
        
        key_players = self.KEY_PLAYERS.get(normalized_team, [])
        if not key_players:
            # Fallback: Team nicht in DB, simuliere mit 0
            return {
                'team': team,
                'normalized': normalized_team,
                'key_players_available': 3,  # Annahme
                'key_players_missing': 0,
                'missing_list': [],
                'impact_score': 0,
                'note': f'Using default (not in database: {team})'
            }
        
        # Simulierte Daten (real würde hier Transfermarkt gescraped werden)
        return {
            'team': team,
            'normalized': normalized_team,
            'key_players_available': len(key_players),
            'key_players_missing': 0,  # Simulation
            'missing_list': [],
            'keeper_missing': False,
            'impact_score': 0,
            'league': self.TEAM_LEAGUE.get(normalized_team, 'Unknown')
        }
    
    def _normalize_team_name(self, team: str) -> str:
        """Normalisiert Team-Namen für Lookup"""
        # Direktes Mapping zuerst
        if team in self.KEY_PLAYERS:
            return team
        
        # Fuzzy matching
        team_lower = team.lower()
        for known_team in self.KEY_PLAYERS:
            known_lower = known_team.lower()
            # Exakte Teilmenge
            if team_lower in known_lower or known_lower in team_lower:
                return known_team
            # Worte prüfen
            team_words = set(team_lower.split())
            known_words = set(known_lower.split())
            if len(team_words & known_words) > 0:
                return known_team
        
        return team
    
    def get_all_teams(self) -> List[str]:
        """Gibt alle 96 unterstützten Teams zurück"""
        return list(self.KEY_PLAYERS.keys())
    
    def get_teams_by_league(self, league: str) -> List[str]:
        """
        Gibt alle Teams einer Liga zurück.
        league: 'D1', 'E0', 'SP1', 'I1', 'F1'
        """
        return [team for team, lg in self.TEAM_LEAGUE.items() if lg == league]


class FootballFormChecker:
    """Checkt Form der letzten 5 Spiele"""
    
    def calculate_form(self, recent_results: List[str]) -> Dict:
        if not recent_results:
            return {'form_score': 50, 'trend': 'unknown', 'confidence_mod': 0}
        
        points = sum([3 if r == 'W' else (1 if r == 'D' else 0) for r in recent_results[:5]])
        max_points = len(recent_results[:5]) * 3
        form_score = (points / max_points * 100) if max_points > 0 else 50
        
        if len(recent_results) >= 3:
            recent = recent_results[:3].count('W')
            if recent >= 2:
                trend = 'positive'
                confidence_mod = 0.05
            elif recent == 0:
                trend = 'negative'
                confidence_mod = -0.05
            else:
                trend = 'mixed'
                confidence_mod = 0
        else:
            trend = 'unknown'
            confidence_mod = 0
        
        return {
            'form_score': round(form_score, 1),
            'trend': trend,
            'last_5': recent_results[:5],
            'confidence_mod': confidence_mod
        }


# Global instances
lineup_scraper = FootballLineupScraper()
form_checker = FootballFormChecker()


if __name__ == "__main__":
    print("[Football Lineup Scraper] Test - Alle 96 Teams")
    
    s = FootballLineupScraper()
    
    # Zeige Statistik
    all_teams = s.get_all_teams()
    print(f"\n📊 Unterstützte Teams: {len(all_teams)}")
    
    # Pro Liga
    for league, name in [('D1', 'Bundesliga'), ('E0', 'Premier League'), 
                         ('SP1', 'La Liga'), ('I1', 'Serie A'), ('F1', 'Ligue 1')]:
        teams = s.get_teams_by_league(league)
        print(f"  {name}: {len(teams)} Teams")
    
    # Test einige Teams
    print("\n=== Test Teams ===")
    for team in ['Bayern Munich', 'Man City', 'Real Madrid', 'Inter', 'PSG']:
        lineup = s.get_team_lineup(team)
        print(f"✅ {team}: {lineup.get('key_players_available', 0)} Key-Player")

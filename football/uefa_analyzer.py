#!/usr/bin/env python3
"""
UEFA Competitions Analyzer (CL, EL, Conference League)
Nutzt CROSS-LEAGUE Mapping: Teams → Liga-Modelle
Unterstützt ALLE 96 Teams aus Top-5-Ligen!
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Load .env from secrets/
env_path = Path(__file__).parent.parent / "secrets" / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ.setdefault(key, value)


sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "src" / "utils"))

from team_database import ALL_TEAMS, TEAM_LEAGUE_MAPPING, UEFA_FALLBACK_TEAMS
from config import config
from model.dixon_coles import DixonColesModel, MatchPrediction
from scraper.theoddsapi import TheOddsAPIClient
from engine.value_engine import ValueEngine
from notifications.telegram import TelegramNotifier

# UEFA Competitions
UEFA_COMPETITIONS = {
    'champions_league': {
        'key': 'soccer_uefa_champions_league',
        'name': 'Champions League',
        'short': 'UCL',
    },
    'europa_league': {
        'key': 'soccer_uefa_europa_league',
        'name': 'Europa League',
        'short': 'UEL',
    },
    'conference_league': {
        'key': 'soccer_uefa_europa_conference_league',
        'name': 'Conference League',
        'short': 'UECL',
    },
}

# Kombiniere alle Mappings
ALL_TEAM_MAPPINGS = {**TEAM_LEAGUE_MAPPING, **UEFA_FALLBACK_TEAMS}


class UEFAAnalyzer:
    """Analyisiert UEFA-Wettbewerbe mit Cross-League Modellen"""
    
    def __init__(self):
        self.api_client = TheOddsAPIClient()
        self.engine = ValueEngine()
        self.notifier = TelegramNotifier()
        self.models_dir = Path("models/leagues")
        self.loaded_models = {}
    
    def _load_model(self, league_code: str) -> Optional[DixonColesModel]:
        if league_code in self.loaded_models:
            return self.loaded_models[league_code]
        
        model_path = self.models_dir / f"dixon_coles_{league_code}.pkl"
        if not model_path.exists():
            return None
        
        try:
            model = DixonColesModel.load(model_path)
            self.loaded_models[league_code] = model
            return model
        except:
            return None
    
    def _get_team_league(self, team_name: str) -> str:
        """Ordnet ein Team seiner Heimliga zu (96+ Teams)"""
        # Direktes Mapping
        if team_name in ALL_TEAM_MAPPINGS:
            return ALL_TEAM_MAPPINGS[team_name]
        
        # Fuzzy: Name enthält bekannten Team-Teil
        for known_team, league in ALL_TEAM_MAPPINGS.items():
            if known_team.lower() in team_name.lower():
                return league
            # Wort-Teile prüfen
            if any(word in team_name.lower() for word in known_team.lower().split()):
                return league
        
        # Fallback: Muster erkennen
        if any(x in team_name.lower() for x in ['madrid', 'barcelona', 'sevilla', 'valencia']):
            return 'SP1'
        if any(x in team_name.lower() for x in ['manchester', 'liverpool', 'london', 'birmingham']):
            return 'E0'
        if 'bayern' in team_name.lower() or 'dortmund' in team_name.lower():
            return 'D1'
        
        print(f"  ⚠️ {team_name}: Unbekannt, verwende E0")
        return 'E0'
    
    def analyze_uefa_match(self, match) -> List:
        home = match.home_team if hasattr(match, 'home_team') else ''
        away = match.away_team if hasattr(match, 'away_team') else ''
        
        home_league = self._get_team_league(home)
        away_league = self._get_team_league(away)
        
        home_model = self._load_model(home_league)
        if not home_model:
            return []
        
        try:
            home_pred = home_model.predict(home, away)
            if not home_pred:
                return []
            
            combined_pred = MatchPrediction(
                home_team=home, away_team=away,
                league=f"UEFA_{home_league}",
                match_date=datetime.now(),
                prob_home_win=home_pred.prob_home_win,
                prob_draw=0.25,
                prob_away_win=1 - home_pred.prob_home_win - 0.25,
                expected_home_goals=1.5,
                expected_away_goals=1.2
            )
            
            mock_odds = type('MockOdds', (), {
                'home_team': home,
                'away_team': away,
                'best_odds_1': match.best_odds_1 if hasattr(match, 'best_odds_1') else 2.0,
                'best_odds_x': match.best_odds_x if hasattr(match, 'best_odds_x') else 3.5,
                'best_odds_2': match.best_odds_2 if hasattr(match, 'best_odds_2') else 3.5,
                'match_datetime': datetime.now(),
                'odds_1': {}, 'odds_x': {}, 'odds_2': {}
            })()
            
            return self.engine.analyze_match(combined_pred, mock_odds)
            
        except Exception as e:
            return []
    
    def analyze_competition(self, competition: str = 'champions_league'):
        if competition not in UEFA_COMPETITIONS:
            print(f"❌ Unbekannt: {competition}")
            return []
        
        info = UEFA_COMPETITIONS[competition]
        print(f"\n{'='*60}")
        print(f"🏆 {info['name']}")
        print(f"{'='*60}")
        print(f"96 Teams → Liga-Modelle (Cross-League)")
        print(f"{'='*60}\n")
        
        try:
            matches = self.api_client.get_live_odds(info['key'])
            print(f"📊 {len(matches)} Spiele\n")
            
            all_bets = []
            for match in matches[:15]:
                bets = self.analyze_uefa_match(match)
                all_bets.extend(bets)
            
            all_bets.sort(key=lambda x: getattr(x, 'value_percentage', 0), reverse=True)
            
            if all_bets:
                print(f"\n🔥 {min(5, len(all_bets))} VALUE-BETS")
                for i, bet in enumerate(all_bets[:5], 1):
                    print(f"{i}. {bet.home_team} vs {bet.away_team}")
            else:
                print("\n❌ Keine Value-Bets")
            
            return all_bets
            
        except Exception as e:
            print(f"❌ {e}")
            return []


def main():
    parser = argparse.ArgumentParser(description="UEFA Competitions Analyzer (96 Teams)")
    parser.add_argument('--competition', default='champions_league',
                       choices=list(UEFA_COMPETITIONS.keys()))
    parser.add_argument('--list', action='store_true', help='Zeige alle 96 Teams')
    
    args = parser.parse_args()
    
    if args.list:
        print(f"Vollständige Datenbank: {len(ALL_TEAMS)} Teams")
        print("\nPro Liga:")
        for lg, name in [('D1','Bundesliga'), ('E0','EPL'), ('SP1','La Liga'), 
                         ('I1','Serie A'), ('F1','Ligue 1')]:
            count = sum(1 for t,l in TEAM_LEAGUE_MAPPING.items() if l==lg)
            print(f"  {name}: {count} Teams")
        return
    
    analyzer = UEFAAnalyzer()
    analyzer.analyze_competition(args.competition)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Multi-League Value Analyzer mit Liga-spezifischen Modellen
Nutzt separate Dixon-Coles Modelle für jede Liga
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config
from model.dixon_coles import DixonColesModel
from scraper.theoddsapi import TheOddsAPIClient
from engine.value_engine import ValueEngine
from notifications.telegram import TelegramNotifier


# TheOddsAPI Sport-Keys
# Domestic Leagues
SUPPORTED_LEAGUES = {
    'bundesliga': {
        'key': 'soccer_germany_bundesliga',
        'name': '1. Bundesliga',
        'model_code': 'D1'
    },
    'bundesliga2': {
        'key': 'soccer_germany_bundesliga_2',
        'name': '2. Bundesliga',
        'model_code': 'D2'
    },
    'epl': {
        'key': 'soccer_epl',
        'name': 'Premier League',
        'model_code': 'E0'
    },
    'laliga': {
        'key': 'soccer_spain_la_liga',
        'name': 'La Liga',
        'model_code': 'SP1'
    },
    'seriea': {
        'key': 'soccer_italy_serie_a',
        'name': 'Serie A',
        'model_code': 'I1'
    },
    'ligue1': {
        'key': 'soccer_france_ligue_one',
        'name': 'Ligue 1',
        'model_code': 'F1'
    },
    'primeira': {
        'key': 'soccer_portugal_primeira_liga',
        'name': 'Primeira Liga',
        'model_code': 'P1'
    },
    'eredivisie': {
        'key': 'soccer_netherlands_eredivisie',
        'name': 'Eredivisie',
        'model_code': 'N1'
    },
}


class MultiLeagueAnalyzer:
    """Analysiert multiple Ligen mit liga-spezifischen Modellen"""
    
    def __init__(self):
        self.api_client = TheOddsAPIClient()
        self.engine = ValueEngine()
        self.notifier = TelegramNotifier()
        self.models_dir = Path("models/leagues")
        self.loaded_models = {}  # Cache für geladene Modelle
    
    def _load_league_model(self, league_code: str):
        """Lädt das liga-spezifische Modell"""
        if league_code in self.loaded_models:
            return self.loaded_models[league_code]
        
        model_path = self.models_dir / f"dixon_coles_{league_code}.pkl"
        
        if not model_path.exists():
            print(f"   ❌ Modell nicht gefunden: {model_path}")
            print(f"   💡 Trainiere zuerst: ./venv/bin/python train_all_leagues.py --league {league_code}")
            return None
        
        try:
            model = DixonColesModel.load(model_path)
            self.loaded_models[league_code] = model
            print(f"   ✅ Modell geladen: {len(model.team_ratings)} Teams")
            return model
        except Exception as e:
            print(f"   ❌ Fehler beim Laden: {e}")
            return None
    
    def analyze_leagues(self, league_codes=None):
        """Analysiert mehrere Ligen"""
        if league_codes is None:
            league_codes = ['bundesliga']
        
        print("=" * 70)
        print("MULTI-LEAGUE VALUE ANALYZER (Liga-spezifische Modelle)")
        print("=" * 70)
        
        all_value_bets = []
        total_matches = 0
        api_calls_used = 0
        
        for code in league_codes:
            if code not in SUPPORTED_LEAGUES:
                print(f"\n❌ Unbekannte Liga: {code}")
                continue
            
            info = SUPPORTED_LEAGUES[code]
            print(f"\n🏆 {info['name']}")
            print("-" * 50)
            
            # Lade liga-spezifisches Modell
            model = self._load_league_model(info['model_code'])
            if not model:
                continue
            
            try:
                # Lade Live-Odds
                matches = self.api_client.get_live_odds(info['key'])
                total_matches += len(matches)
                
                if not matches:
                    print("   ⚠️  Keine Spiele gefunden")
                    continue
                
                print(f"   📊 {len(matches)} Matches geladen")
                
                # Konvertiere
                odds_list = self.api_client.convert_to_odds_data(matches)
                
                # Analysiere mit Liga-spezifischem Modell
                bets = self._analyze_matches(odds_list, model)
                
                if bets:
                    print(f"   🔥 {len(bets)} Value-Bets:")
                    for b in bets[:3]:
                        emoji = "🟢" if b.confidence == 'high' else "🟡"
                        print(f"      {emoji} {b.home_team} vs {b.away_team}")
                        print(f"         {b.selection} @ {b.best_odds:.2f} ({b.value_percentage:.1%})")
                    all_value_bets.extend(bets)
                else:
                    print("   📭 Keine Value-Bets")
                    
            except Exception as e:
                print(f"   ❌ Fehler: {e}")
        
        # Sortiere alle
        all_value_bets.sort(key=lambda x: x.value_percentage, reverse=True)
        
        # Zeige finale Ergebnisse
        self._display_final_results(all_value_bets, total_matches, league_codes)
        
        # Sende Alerts
        if all_value_bets and self.notifier.is_configured():
            alerts = [vb for vb in all_value_bets 
                     if vb.confidence in ['high', 'medium']][:10]
            if alerts:
                print(f"\n📱 Sende {len(alerts)} Telegram Alerts...")
                success = self.notifier.sync_send_alert(alerts)
                print(f"   {'✅' if success else '❌'} Alerts")
        
        return all_value_bets
    
    def _analyze_matches(self, odds_list, model):
        """Analysiert Matches mit spezifischem Modell"""
        value_bets = []
        
        for odds in odds_list:
            # Team-Namen normalisieren
            home_norm = self._normalize_name(odds.home_team)
            away_norm = self._normalize_name(odds.away_team)
            
            # Vorhersage mit Liga-spezifischem Modell
            pred = model.predict(home_norm, away_norm)
            
            if pred:
                # Original-Namen für Display
                pred.home_team = odds.home_team
                pred.away_team = odds.away_team
                
                # Berechne Value
                bets = self.engine.analyze_match(pred, odds)
                value_bets.extend(bets)
        
        return value_bets
    
    def _normalize_name(self, name):
        """Normalisiert Team-Namen für Modell-Lookup"""
        mappings = {
            # England
            'Manchester City': 'Man City',
            'Manchester United': 'Man United',
            'Brighton and Hove Albion': 'Brighton',
            'Tottenham Hotspur': 'Tottenham',
            'Newcastle United': 'Newcastle',
            'Wolverhampton Wanderers': 'Wolves',
            'West Ham United': 'West Ham',
            'Nottingham Forest': "Nott'm Forest",
            
            # Spanien
            'Atletico Madrid': 'Ath Madrid',
            'Atletico de Madrid': 'Ath Madrid',
            'Real Betis': 'Betis',
            
            # Italien
            'Internazionale': 'Inter',
            'AC Milan': 'Milan',
            'AS Roma': 'Roma',
            'SSC Napoli': 'Napoli',
            'Juventus Turin': 'Juventus',
            'Juventus': 'Juventus',
            
            # Deutschland (Fallback)
            'Bayern Munich': 'Bayern Munich',
            'Bayer Leverkusen': 'Leverkusen',
            'Borussia Dortmund': 'Dortmund',
            'RB Leipzig': 'RB Leipzig',
        }
        return mappings.get(name, name)
    
    def _display_final_results(self, value_bets, total_matches, leagues):
        """Zeigt finale Ergebnisse"""
        print(f"\n{'='*70}")
        print(f"🔥 TOP {min(10, len(value_bets))} VALUE-BETS")
        print(f"{'='*70}")
        
        if not value_bets:
            print("\n📭 Keine Value-Bets gefunden")
            return
        
        for i, bet in enumerate(value_bets[:10], 1):
            emoji = "🟢" if bet.confidence == 'high' else ("🟡" if bet.confidence == 'medium' else "⚪")
            print(f"\n{i:2d}. {emoji} {bet.home_team} vs {bet.away_team}")
            print(f"    💰 {bet.selection} @ {bet.best_odds:.2f} @ {bet.bookmaker}")
            print(f"    🧠 Modell: {bet.model_probability:.1%} | 📈 Market: {bet.market_probability:.1%}")
            print(f"    ⚡ VALUE: {bet.value_percentage:.1%} | EV: {bet.roi:+.1f}%")
            print(f"    🎯 Kelly: {bet.kelly_stake:.0f} coins")
        
        print(f"\n{'='*70}")
        print(f"📊 GESAMT: {len(value_bets)} Value-Bets aus {total_matches} Matches")
        print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(description="Multi-League Value Analyzer")
    parser.add_argument('--leagues', nargs='+', default=['bundesliga'],
                       choices=list(SUPPORTED_LEAGUES.keys()),
                       help='Ligen zu analysieren')
    parser.add_argument('--list', action='store_true',
                       help='Zeige verfügbare Ligen')
    
    args = parser.parse_args()
    
    if args.list:
        print("Verfügbare Ligen:")
        for code, info in SUPPORTED_LEAGUES.items():
            print(f"  {code:15s} - {info['name']}")
        return
    
    analyzer = MultiLeagueAnalyzer()
    analyzer.analyze_leagues(args.leagues)


if __name__ == "__main__":
    main()
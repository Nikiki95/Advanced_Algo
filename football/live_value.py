#!/usr/bin/env python3
"""
LIVE VALUE ANALYZER
Nutzt TheOddsAPI für aktuelle Quoten
Kombiniert mit Dixon-Coles Modell
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config
from data.loader import FootballDataLoader
from model.dixon_coles import DixonColesModel
from scraper.theoddsapi import TheOddsAPIClient
from engine.value_engine import ValueEngine


class LiveValueAnalyzer:
    """
    ECHTE Live Value-Bet Analyse mit TheOddsAPI
    """
    
    def __init__(self):
        self.data_loader = FootballDataLoader()
        self.model = None
        self.api_client = None
        self.engine = ValueEngine()
        self.models_dir = Path("models")
        
        try:
            self.api_client = TheOddsAPIClient()
            print("✅ TheOddsAPI verbunden")
        except Exception as e:
            print(f"❌ TheOddsAPI Fehler: {e}")
    
    def analyze_live_matches(self):
        """
        Haupt-Workflow mit LIVE Odds
        """
        print(f"\n{'='*70}")
        print(f"📊 LIVE VALUE ANALYZER (TheOddsAPI)")
        print(f"{'='*70}")
        
        # 1. Trainiere Modell
        print("\n[1/4] Lade & trainiere Modell...")
        model_path = self.models_dir / "dixon_coles_latest.pkl"
        
        if model_path.exists():
            self.model = DixonColesModel.load(model_path)
            print(f"   ✅ Geladen: {len(self.model.team_ratings)} Teams")
        else:
            df = self.data_loader.load_training_data(leagues=['D1'])
            self.model = DixonColesModel(rho=config.DC_RHO)
            self.model.fit(df)
            self.model.save(model_path)
        
        # 2. Lade LIVE Odds
        print("\n[2/4] Lade LIVE Odds von TheOddsAPI...")
        
        if not self.api_client:
            print("   ❌ Kein API Client verfügbar")
            return
        
        matches = self.api_client.get_live_odds('soccer_germany_bundesliga')
        
        if not matches:
            print("   ❌ Keine Matches gefunden")
            return
        
        print(f"   ✅ {len(matches)} Live-Matches geladen")
        
        # 3. Konvertiere zu OddsData
        print("\n[3/4] Konvertiere Odds...")
        odds_list = self.api_client.convert_to_odds_data(matches)
        print(f"   ✅ {len(odds_list)} Matches ready")
        
        # 4. Analysiere jedes Match
        print("\n[4/4] Analysiere Value...")
        value_bets = []
        
        for odds_data in odds_list:
            # Modell-Vorhersage
            pred = self.model.predict(odds_data.home_team, odds_data.away_team)
            
            if not pred:
                # Team-Name Mismatch? Versuche Normalisierung
                home_norm = self._normalize_team_name(odds_data.home_team)
                away_norm = self._normalize_team_name(odds_data.away_team)
                pred = self.model.predict(home_norm, away_norm)
                
                if not pred:
                    print(f"   ⚠️  Überspringe: {odds_data.home_team} vs {odds_data.away_team}")
                    continue
            
            # Berechne Value
            bets = self.engine.analyze_match(pred, odds_data)
            value_bets.extend(bets)
        
        # Sortiere nach Value
        value_bets.sort(key=lambda x: x.value_percentage, reverse=True)
        
        # Zeige Ergebnisse
        self._display_results(value_bets, odds_list)
        
        return value_bets
    
    def _normalize_team_name(self, name: str) -> str:
        """Normalisiert Team-Namen für Modell-Lookup (1. & 2. Liga)"""
        mappings = {
            # 1. Bundesliga
            'Eintracht Frankfurt': 'Ein Frankfurt',
            '1. FC Heidenheim': 'Heidenheim',
            'Borussia Dortmund': 'Dortmund',
            'FC Augsburg': 'Augsburg',
            'Bayern Munich': 'Bayern Munich',
            'Bayern München': 'Bayern Munich',
            'Bayer Leverkusen': 'Leverkusen',
            'RB Leipzig': 'RB Leipzig',
            'VfB Stuttgart': 'Stuttgart',
            'SC Freiburg': 'Freiburg',
            'Werder Bremen': 'Werder Bremen',
            '1. FC Union Berlin': 'Union Berlin',
            '1. FSV Mainz 05': 'Mainz',
            'FSV Mainz 05': 'Mainz',
            'VfL Wolfsburg': 'Wolfsburg',
            'Borussia Mönchengladbach': "M'gladbach",
            'Borussia Monchengladbach': "M'gladbach",
            "TSG 1899 Hoffenheim": 'Hoffenheim',
            'TSG Hoffenheim': 'Hoffenheim',
            'FC St. Pauli': 'St Pauli',
            'Holstein Kiel': 'Holstein Kiel',
            
            # 2. Bundesliga (wenn vorhanden im Modell)
            'Hamburger SV': 'Hamburg',
            '1. FC Köln': 'FC Koln',
            '1. FC Koln': 'FC Koln',
            'FC Schalke 04': 'Schalke',
            'Hertha BSC': 'Hertha',
            'Karlsruher SC': 'Karlsruhe',
            'SV Darmstadt 98': 'Darmstadt',
            'SC Paderborn 07': 'Paderborn',
            'Fortuna Dusseldorf': 'Fortuna Dusseldorf',
            'Fortuna Düsseldorf': 'Fortuna Dusseldorf',
            'Hannover 96': 'Hannover',
            '1. FC Nürnberg': 'Nurnberg',
            'Eintracht Braunschweig': 'Braunschweig',
            'SSV Jahn Regensburg': 'Regensburg',
            'SV Elversberg': 'Elversberg',
            'Preußen Münster': 'Preussen Munster',
            'Greuther Fürth': 'Greuther Furth',
            'SV Wehen Wiesbaden': 'Wehen',
            'SSV Ulm 1846': 'Ulm',
        }
        return mappings.get(name, name)
    
    def analyze_bundesliga_2(self):
        """Analysiert 2. Bundesliga"""
        print(f"\n{'='*70}")
        print(f"📊 2. BUNDESLIGA - LIVE VALUE ANALYZER")
        print(f"{'='*70}")
        
        if not self.api_client:
            print("❌ Kein API Client verfügbar")
            return
        
        # 2. Liga hat oft eigenen Sport-Key
        try:
            matches = self.api_client.get_live_odds('soccer_germany_bundesliga_2')
            print(f"✅ {len(matches)} 2.Liga-Matches geladen")
            
            # Konvertiere & analysiere
            odds_list = self.api_client.convert_to_odds_data(matches)
            
            value_bets = []
            for odds_data in odds_list:
                # Versuche Vorhersage mit 2.Liga-Modell (simpler)
                pred = self._predict_with_fallback(odds_data)
                if pred:
                    bets = self.engine.analyze_match(pred, odds_data)
                    value_bets.extend(bets)
            
            value_bets.sort(key=lambda x: x.value_percentage, reverse=True)
            self._display_results(value_bets, odds_list, title="2. BUNDESLIGA")
            
        except Exception as e:
            print(f"⚠️  2.Liga nicht verfügbar: {e}")
            print("   (Möglicherweise hat TheOddsAPI keinen separaten Key für 2.Liga)")
    
    def _predict_with_fallback(self, odds_data):
        """Simple Vorhersage für Teams ohne DC-Training (2.Liga Fallback)"""
        from model.dixon_coles import MatchPrediction
        
        home = odds_data.home_team
        away = odds_data.away_team
        
        # Versuche DC-Modell
        pred = self.model.predict(home, away)
        if pred:
            return pred
        
        # Versuche mit normalisierten Namen
        home_norm = self._normalize_team_name(home)
        away_norm = self._normalize_team_name(away)
        pred = self.model.predict(home_norm, away_norm)
        if pred:
            return pred
        
        # Fallback: Basierend auf Odds + Heimvorteil
        best_home = max(odds_data.odds_1.values()) if odds_data.odds_1 else 2.5
        best_away = max(odds_data.odds_2.values()) if odds_data.odds_2 else 3.0
        
        # Implied probs mit Heimvorteil
        imp_home = 1 / best_home
        imp_away = 1 / best_away
        total = imp_home + imp_away + 0.3  # +30% für Draw
        
        prob_home = (imp_home / total) * 1.1  # Heimvorteil
        prob_away = imp_away / total
        prob_draw = 1 - prob_home - prob_away
        
        return MatchPrediction(
            home_team=home,
            away_team=away,
            league="D2",
            match_date=odds_data.match_datetime,
            prob_home_win=max(0, prob_home),
            prob_draw=max(0, prob_draw),
            prob_away_win=max(0, prob_away),
            expected_home_goals=1.5,
            expected_away_goals=1.2,
            score_matrix=None
        )
    
    def _display_results(self, value_bets, all_matches):
        """Zeigt Ergebnisse"""
        print(f"\n{'='*70}")
        print(f"🔥 LIVE VALUE-BET ALERTS")
        print(f"🔴 TheOddsAPI - Aktuelle Quoten")
        print(f"{'='*70}")
        
        # Zeige alle Matches mit ihren besten Odds
        print(f"\n📋 Gescrapte Matches ({len(all_matches)}):")
        for m in all_matches:
            best_1 = max(m.odds_1.values()) if m.odds_1 else 0
            best_x = max(m.odds_x.values()) if m.odds_x else 0
            best_2 = max(m.odds_2.values()) if m.odds_2 else 0
            print(f"  • {m.home_team} vs {m.away_team}")
            print(f"    1: {best_1:.2f} | X: {best_x:.2f} | 2: {best_2:.2f}")
        
        print(f"\n{'='*70}")
        
        if not value_bets:
            print("\n📭 Keine Value-Bets gefunden")
            print(f"\n💡 Tipp: Threshold ist {config.MIN_VALUE_THRESHOLD}")
            return
        
        print(f"\n🎯 Gefunden: {len(value_bets)} Value-Bets\n")
        
        for i, bet in enumerate(value_bets[:10], 1):
            emoji = "🟢" if bet.confidence == 'high' else ("🟡" if bet.confidence == 'medium' else "⚪")
            
            print(f"{i:2d}. {emoji} {bet.home_team} vs {bet.away_team}")
            print(f"    💰 Wette: {bet.selection} ({bet.bet_type})")
            print(f"    📊 Quote: {bet.best_odds:.2f} @{bet.bookmaker}")
            print(f"    🧠 Modell: {bet.model_probability:.1%}")
            print(f"    📈 Market: {bet.market_probability:.1%}")
            print(f"    ⚡ VALUE: {bet.value_percentage:.1%} | EV: {bet.roi:+.1f}%")
            print(f"    🎯 Kelly: {bet.kelly_stake:.0f} coins")
            date_str = bet.match_datetime.strftime('%a %d.%m.%H:%M') if bet.match_datetime else 'TBD'
            print(f"    📅 {date_str}")
            print()
        
        print(f"{'='*70}")
        print("⚠️  Dies sind echte Live-Quoten von TheOddsAPI!")
        print("   Wette manuell bei bet365 oder deinem Bookie.")
        print(f"{'='*70}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Value-Bet Analyzer")
    parser.add_argument("--threshold", type=float, default=None, help="Value-Threshold")
    args = parser.parse_args()
    
    if args.threshold:
        import os
        os.environ['MIN_VALUE_THRESHOLD'] = str(args.threshold)
        from importlib import reload
        import config as cfg
        reload(cfg)
    
    analyzer = LiveValueAnalyzer()
    analyzer.analyze_live_matches()


if __name__ == "__main__":
    main()
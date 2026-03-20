#!/usr/bin/env python3
"""
Historical Value Mode
Nutzt Closing Odds aus football-data.co.uk als Proxy für aktuelle Quoten
Keine Live-API nötig, 100% kostenlos
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config
from data.loader import FootballDataLoader
from model.dixon_coles import DixonColesModel
from engine.value_engine import ValueEngine


class HistoricalValueAnalyzer:
    """
    Analysiert Value auf Basis historischer Closing Odds
    Das ist legal, kostenlos, und gibt dir einen guten Proxy für Markt-Richtung
    """
    
    def __init__(self):
        self.data_loader = FootballDataLoader()
        self.model = None
        self.engine = ValueEngine()
        self.models_dir = Path("models")
        self.models_dir.mkdir(exist_ok=True)
    
    def analyze_current_fixtures(self, league: str = "D1"):
        """
        Haupt-Workflow:
        1. Trainiere Modell auf historischen Daten
        2. Lade aktuelle Fixtures mit Closing Odds
        3. Berechne Value
        """
        print(f"\n{'='*70}")
        print(f"📊 HISTORICAL VALUE ANALYZER")
        print(f"{'='*70}")
        
        # 1. Trainiere Modell
        print("\n[1/4] Trainiere Modell...")
        model_path = self.models_dir / "dixon_coles_latest.pkl"
        
        if model_path.exists():
            self.model = DixonColesModel.load(model_path)
            print(f"   Geladen: {len(self.model.team_ratings)} Teams")
        else:
            df = self.data_loader.load_training_data(leagues=[league])
            self.model = DixonColesModel(rho=config.DC_RHO)
            self.model.fit(df)
            self.model.save(model_path)
        
        # 2. Lade aktuelle Fixtures
        print(f"\n[2/4] Lade kommende Spiele aus {league}...")
        fixtures = self.data_loader.get_upcoming_fixtures(league)
        
        if fixtures.empty:
            print("   ❌ Keine Fixtures gefunden")
            return
        
        print(f"   ✅ {len(fixtures)} Spiele gefunden")
        
        # 3. Extrahiere Odds
        print("\n[3/4] Extrahiere Odds...")
        fixtures = self.data_loader.get_match_odds(fixtures, bookmaker="B365")
        
        # Filter auf gültige Odds
        fixtures = fixtures[
            fixtures['odds_1'].notna() & 
            fixtures['odds_x'].notna() & 
            fixtures['odds_2'].notna()
        ].copy()
        
        print(f"   ✅ {len(fixtures)} Spiele mit Odds")
        
        # 4. Berechne Vorhersagen & Value
        print("\n[4/4] Analysiere Value...")
        value_bets = []
        
        for _, row in fixtures.iterrows():
            # Modell-Vorhersage
            pred = self.model.predict(row['HomeTeam'], row['AwayTeam'])
            
            if not pred:
                continue
            
            # Erstelle Mock-OddsData für Value Engine
            from scraper.sbr_scraper import OddsData
            
            odds_data = OddsData(
                event_id="hist_" + str(hash(row['HomeTeam'] + row['AwayTeam'])),
                match_name=f"{row['HomeTeam']} vs {row['AwayTeam']}",
                home_team=row['HomeTeam'],
                away_team=row['AwayTeam'],
                league=league,
                match_datetime=pd.to_datetime(row['Date']),
                odds_1={'bet365': row['odds_1']},
                odds_x={'bet365': row['odds_x']},
                odds_2={'bet365': row['odds_2']},
                implied_prob_1=1/row['odds_1'],
                implied_prob_x=1/row['odds_x'],
                implied_prob_2=1/row['odds_2'],
                overround=0.0,
                timestamp=datetime.now()
            )
            
            # Berechne Value
            bets = self.engine.analyze_match(pred, odds_data)
            value_bets.extend(bets)
        
        # Sortiere nach Value
        value_bets.sort(key=lambda x: x.value_percentage, reverse=True)
        
        # Zeige Ergebnisse
        self._display_results(value_bets)
        
        return value_bets
    
    def _display_results(self, value_bets):
        """Zeigt Ergebnisse an"""
        print(f"\n{'='*70}")
        print(f"🔥 VALUE-BET ALERTS (Historical Odds)")
        print(f"{'='*70}")
        
        if not value_bets:
            print("\n📭 Keine Value-Bets gefunden")
            print(f"\n💡 Tipp: Threshold ist {config.MIN_VALUE_THRESHOLD},")
            print("   versuche --threshold 0.02 für weniger strenge Filter")
            return
        
        print(f"\nGefunden: {len(value_bets)} Value-Bets\n")
        
        for i, bet in enumerate(value_bets[:10], 1):
            emoji = "🟢" if bet.confidence == 'high' else ("🟡" if bet.confidence == 'medium' else "⚪")
            
            print(f"{i:2d}. {emoji} {bet.home_team} vs {bet.away_team}")
            print(f"    Wette: {bet.selection} ({bet.bet_type})")
            print(f"    Quote: {bet.best_odds:.2f}")
            print(f"    Modell: {bet.model_probability:.1%} | Market: {bet.market_probability:.1%}")
            print(f"    ⚡ VALUE: {bet.value_percentage:.1%} | EV: {bet.roi:+.1f}%")
            print(f"    Kelly: {bet.kelly_stake:.0f} coins")
            date_str = bet.match_datetime.strftime('%a %d.%m.%H:%M') if bet.match_datetime else 'TBD'
            print(f"    📅 {date_str}")
            print()
        
        print(f"{'='*70}")
        print("⚠️  Hinweis: Diese Odds sind 'Closing Odds' aus den Daten.")
        print("    Aktuelle Live-Quoten können davon abweichen!")
        print(f"{'='*70}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Value-Bet Analyzer mit historischen Odds (kostenlos)"
    )
    parser.add_argument(
        "--league", 
        default="D1", 
        choices=["D1", "D2"],
        help="Liga: D1=Bundesliga, D2=2.Bundesliga"
    )
    parser.add_argument(
        "--threshold", 
        type=float,
        default=None,
        help="Value-Threshold (default: 0.05 = 5%)"
    )
    
    args = parser.parse_args()
    
    if args.threshold:
        # Temporär override
        import os
        os.environ['MIN_VALUE_THRESHOLD'] = str(args.threshold)
        # Reload config
        from importlib import reload
        import config as cfg_module
        reload(cfg_module)
    
    analyzer = HistoricalValueAnalyzer()
    analyzer.analyze_current_fixtures(args.league)


if __name__ == "__main__":
    main()
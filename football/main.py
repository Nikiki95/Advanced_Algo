#!/usr/bin/env python3
"""
Value-Bet Algorithm für Bundesliga
Kombiniert Dixon-Coles Modell mit SBR Odds-Scraping
"""
import os
import sys
import asyncio
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

# Füge src zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config
from data.loader import FootballDataLoader
from model.dixon_coles import DixonColesModel
from scraper.sbr_scraper import SBRScraper, MockSBRScraper
from scraper.theoddsapi import TheOddsAPIClient
from engine.value_engine import ValueEngine
from notifications.telegram import TelegramNotifier


class ValueBetAlgorithm:
    """
    Haupt-Klasse für den Value-Bet Algorithmus
    """
    
    def __init__(self):
        self.data_loader = FootballDataLoader()
        self.model = None
        self.scraper = SBRScraper()
        self.value_engine = ValueEngine()
        self.notifier = TelegramNotifier()
        
        # Verzeichnisse
        self.models_dir = Path("models")
        self.models_dir.mkdir(exist_ok=True)
        
    def train_model(self, force_retrain: bool = False) -> DixonColesModel:
        """
        Trainiert oder lädt das Dixon-Coles Modell
        """
        model_path = self.models_dir / "dixon_coles_latest.pkl"
        
        # Prüfe ob aktuelles Modell existiert
        if model_path.exists() and not force_retrain:
            print(f"[System] Lade bestehendes Modell...")
            self.model = DixonColesModel.load(model_path)
            
            # Prüfe Alter des Modells
            if self.model.training_date:
                age_days = (datetime.now() - self.model.training_date).days
                if age_days > 1:
                    print(f"[System] Modell ist {age_days} Tage alt - Retrainiere...")
                else:
                    print(f"[System] Modell ist aktuell ({age_days}h alt)")
                    return self.model
        
        # Lade Trainingsdaten
        print("[System] Lade historische Daten...")
        df = self.data_loader.load_training_data()
        
        if len(df) < 100:
            print(f"[Error] Nur {len(df)} Spiele gefunden - zu wenig für Training")
            sys.exit(1)
        
        print(f"[System] {len(df)} Spiele geladen")
        
        # Trainiere Modell
        self.model = DixonColesModel(rho=config.DC_RHO)
        self.model.fit(df)
        
        # Speichere Modell
        self.model.save(model_path)
        
        return self.model
    
    def find_value_bets(self, league: str = "bundesliga") -> List:
        """
        Haupt-Workflow: Scrape Odds → Analysiere → Finde Value
        """
        if self.model is None:
            self.train_model()
        
        print(f"\n[Workflow] Suche Value-Bets für {league}...")
        
        # 1. Hole kommende Matches mit Odds
        print("[1/3] Scrape Odds von SBR...")
        matches = self.scraper.get_upcoming_matches(league, days=2)
        
        if not matches:
            print("[Error] Keine Matches mit Odds gefunden")
            return []
        
        print(f"[OK] {len(matches)} Matches gefunden")
        
        # 2. Erstelle Vorhersagen
        print("[2/3] Erstelle Modell-Vorhersagen...")
        
        # Konvertiere zu DataFrame für Prediction
        fixtures = []
        for m in matches:
            fixtures.append({
                'HomeTeam': m.home_team,
                'AwayTeam': m.away_team,
                'Date': m.match_datetime,
                'League': m.league
            })
        
        fixtures_df = __import__('pandas', fromlist=['DataFrame']).DataFrame(fixtures)
        predictions = self.model.predict_matches(fixtures_df)
        
        print(f"[OK] {len(predictions)} Vorhersagen erstellt")
        
        # 3. Finde Value-Bets
        print("[3/3] Vergleiche Modell mit Market...")
        
        all_value_bets = []
        
        for match in matches:
            # Finde passende Prediction
            pred = next((p for p in predictions 
                        if p.home_team == match.home_team and p.away_team == match.away_team), None)
            
            if not pred:
                continue
            
            # Analysiere auf Value
            value_bets = self.value_engine.analyze_match(pred, match)
            all_value_bets.extend(value_bets)
        
        # Sortiere nach Value
        all_value_bets.sort(key=lambda x: x.value_percentage, reverse=True)
        
        print(f"\n[Ergebnis] {len(all_value_bets)} Value-Bets gefunden")
        
        return all_value_bets
    
    def display_results(self, value_bets: List):
        """Zeigt Ergebnisse in der Konsole"""
        if not value_bets:
            print("\n📭 Keine Value-Bets gefunden")
            return
        
        print("\n" + "="*80)
        print("🔥 VALUE-BET ALERTS")
        print("="*80)
        
        for bet in value_bets[:10]:  # Top 10
            emoji = "🟢" if bet.confidence == 'high' else ("🟡" if bet.confidence == 'medium' else "⚪")
            
            print(f"\n{emoji} {bet.home_team} vs {bet.away_team}")
            print(f"   Wette: {bet.selection} ({bet.bet_type})")
            print(f"   Quote: {bet.best_odds:.2f} @{bet.bookmaker}")
            print(f"   Modell: {bet.model_probability:.1%}")
            print(f"   Market: {bet.market_probability:.1%}")
            print(f"   Value:  {bet.value_percentage:.1%} (EV: {bet.roi:+.1f}%)")
            print(f"   Kelly:  {bet.kelly_stake:.0f} coins")
            print(f"   Zeit:   {bet.match_datetime.strftime('%a %H:%M')}")
        
        print("\n" + "="*80)
    
    async def run_with_notifications(self, league: str = "bundesliga"):
        """Haupt-Loop mit Telegram-Benachrichtigungen"""
        value_bets = self.find_value_bets(league)
        
        # Zeige in Konsole
        self.display_results(value_bets)
        
        # Sende Telegram wenn konfiguriert
        if self.notifier.is_configured() and value_bets:
            await self.notifier.send_alert(value_bets)


def main():
    """CLI Entry Point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Value-Bet Algorithm")
    parser.add_argument("--train", action="store_true", help="Force model retraining")
    parser.add_argument("--league", default="bundesliga", help="Liga (bundesliga, premier-league)")
    parser.add_argument("--test-telegram", action="store_true", help="Test Telegram integration")
    parser.add_argument("--no-notify", action="store_true", help="Keine Benachrichtigungen senden")
    
    args = parser.parse_args()
    
    algo = ValueBetAlgorithm()
    
    # Optional: Test Telegram
    if args.test_telegram:
        asyncio.run(algo.notifier.send_test_message())
        return
    
    # Trainiere Modell
    algo.train_model(force_retrain=args.train)
    
    # Führe Analyse aus
    if args.no_notify:
        value_bets = algo.find_value_bets(args.league)
        algo.display_results(value_bets)
    else:
        asyncio.run(algo.run_with_notifications(args.league))


if __name__ == "__main__":
    main()

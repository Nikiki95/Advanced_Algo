#!/usr/bin/env python3
"""
Test-Script für das Value-Bet Algorithm
Dry-Run mit Mock-Daten - keine externen APIs nötig
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Füge src zum Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config
from model.dixon_coles import DixonColesModel, MatchPrediction, TeamStrength
from scraper.sbr_scraper import OddsData, MockSBRScraper
from engine.value_engine import ValueEngine, ValueBet
from notifications.telegram import TelegramNotifier


class DryRunTester:
    """
    Testet alle Komponenten mit Mock-Daten
    Keine externen API-Calls!
    """
    
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.errors = []
        
    def log(self, message: str, level: str = "info"):
        """Loggt mit Farben"""
        colors = {
            "info": "\033[94m",     # Blau
            "success": "\033[92m",  # Grün
            "warning": "\033[93m", # Gelb
            "error": "\033[91m",    # Rot
            "reset": "\033[0m"
        }
        color = colors.get(level, colors["info"])
        print(f"{color}[{level.upper()}]\033[0m {message}")
    
    def check(self, name: str, condition: bool, details: str = "") -> bool:
        """Führt einen Check durch"""
        if condition:
            self.checks_passed += 1
            self.log(f"✅ {name}", "success")
            if details:
                print(f"   {details}")
            return True
        else:
            self.checks_failed += 1
            self.log(f"❌ {name}", "error")
            if details:
                print(f"   {details}")
            return False
    
    def test_config(self) -> bool:
        """Test 1: Konfiguration laden"""
        self.log("\n📋 Test 1: Konfiguration", "info")
        
        checks = [
            self.check("Config geladen", config is not None),
            self.check("LEAGUES definiert", len(config.LEAGUES) > 0, f"Ligen: {config.LEAGUES}"),
            self.check("MIN_VALUE_THRESHOLD", config.MIN_VALUE_THRESHOLD > 0, f"Threshold: {config.MIN_VALUE_THRESHOLD}"),
            self.check("TRAINING_YEARS", config.TRAINING_YEARS >= 1, f"Jahre: {config.TRAINING_YEARS}"),
        ]
        
        return all(checks)
    
    def test_model(self) -> bool:
        """Test 2: Dixon-Coles Modell (mit Mock-Daten)"""
        self.log("\n🧠 Test 2: Dixon-Coles Modell", "info")
        
        try:
            # Erstelle Mock-Trainingsdaten
            import pandas as pd
            
            mock_data = []
            teams = ["Bayern Munich", "Dortmund", "Leipzig", "Leverkusen", "Stuttgart", "Frankfurt"]
            
            for i in range(100):  # 100 Mock-Spiele
                home = teams[i % len(teams)]
                away = teams[(i + 1) % len(teams)]
                
                mock_data.append({
                    'Date': datetime.now() - timedelta(days=i*7),
                    'HomeTeam': home,
                    'AwayTeam': away,
                    'FTHG': np.random.poisson(1.8),  # Durchschnitt 1.8 Heimtore
                    'FTAG': np.random.poisson(1.2),  # Durchschnitt 1.2 Auswärtstore
                })
            
            df = pd.DataFrame(mock_data)
            
            # Teste Modell-Training
            model = DixonColesModel(rho=-0.13)
            model.fit(df)
            
            checks = [
                self.check("Modell trainiert", model.fitted_model is not None or len(model.team_ratings) > 0),
                self.check(f"Team-Ratings berechnet", len(model.team_ratings) > 0, f"Teams: {len(model.team_ratings)}"),
            ]
            
            # Teste Vorhersage
            pred = model.predict("Bayern Munich", "Dortmund")
            
            if pred:
                checks.extend([
                    self.check("Vorhersage erstellt", pred is not None),
                    self.check("Probs summieren zu ~1", 
                              abs(pred.prob_home_win + pred.prob_draw + pred.prob_away_win - 1.0) < 0.01,
                              f"Sum: {pred.prob_home_win + pred.prob_draw + pred.prob_away_win:.3f}"),
                    self.check("Expected Goals berechnet", pred.expected_home_goals > 0 and pred.expected_away_goals > 0,
                              f"xG: {pred.expected_home_goals:.2f} - {pred.expected_away_goals:.2f}"),
                ])
            
            # Teste Speichern/Laden
            model_path = Path("models/test_model.pkl")
            model.save(model_path)
            loaded = DixonColesModel.load(model_path)
            
            checks.append(
                self.check("Modell speichern/laden", loaded is not None)
            )
            
            # Cleanup
            if model_path.exists():
                model_path.unlink()
            
            return all(checks)
            
        except Exception as e:
            self.check("Modell-Test", False, str(e))
            return False
    
    def test_scraper(self) -> bool:
        """Test 3: Scraper (Mock-Modus)"""
        self.log("\n🔍 Test 3: Scraper (Mock)", "info")
        
        try:
            scraper = MockSBRScraper()
            matches = scraper.get_upcoming_matches("bundesliga")
            
            checks = [
                self.check("Mock-Scraper initialisiert", scraper is not None),
                self.check("Mock-Matches generiert", len(matches) > 0, f"Matches: {len(matches)}"),
            ]
            
            if matches:
                match = matches[0]
                checks.extend([
                    self.check("Match hat alle Daten", 
                              match.home_team and match.away_team and match.best_odds > 0),
                    self.check("Implied Probs berechnet",
                              match.implied_prob_1 + match.implied_prob_x + match.implied_prob_2 > 0),
                ])
            
            return all(checks)
            
        except Exception as e:
            self.check("Scraper-Test", False, str(e))
            return False
    
    def test_value_engine(self) -> bool:
        """Test 4: Value Engine"""
        self.log("\n💰 Test 4: Value Engine", "info")
        
        try:
            engine = ValueEngine()
            
            # Erstelle Mock-Prediction und Odds
            from dataclasses import dataclass
            from datetime import datetime
            
            @dataclass
            class MockPred:
                home_team: str = "Bayern"
                away_team: str = "Dortmund"
                match_date: datetime = None
                prob_home_win: float = 0.65
                prob_draw: float = 0.20
                prob_away_win: float = 0.15
                expected_home_goals: float = 2.1
                expected_away_goals: float = 1.2
                
            @dataclass
            class MockOdds:
                home_team: str = "Bayern"
                away_team: str = "Dortmund"
                odds_1: dict = None
                odds_x: dict = None
                odds_2: dict = None
                implied_prob_1: float = 0.56
                implied_prob_x: float = 0.24
                implied_prob_2: float = 0.22
                
                def __post_init__(self):
                    if self.odds_1 is None:
                        self.odds_1 = {"bet365": 1.80}
                    if self.odds_x is None:
                        self.odds_x = {"bet365": 3.60}
                    if self.odds_2 is None:
                        self.odds_2 = {"bet365": 4.50}
            
            mock_pred = MockPred(match_date=datetime.now())
            mock_odds = MockOdds()
            
            # Teste Value-Berechnung
            value_bets = engine.analyze_match(mock_pred, mock_odds, bankroll=1000.0)
            
            checks = [
                self.check("Value Engine initialisiert", engine is not None),
                self.check("Value-Bets gefunden", len(value_bets) > 0, f"Bets: {len(value_bets)}"),
            ]
            
            if value_bets:
                bet = value_bets[0]
                checks.extend([
                    self.check("Value positiv", bet.value_percentage > 0, f"Value: {bet.value_percentage:.2%}"),
                    self.check("EV berechnet", bet.expected_value > 0, f"EV: {bet.expected_value:.3f}"),
                    self.check("Kelly berechnet", bet.kelly_stake > 0, f"Kelly: {bet.kelly_stake:.0f}"),
                    self.check("Konfidenz zugewiesen", bet.confidence in ['high', 'medium', 'low']),
                ])
            
            return all(checks)
            
        except Exception as e:
            self.check("Value-Engine-Test", False, str(e))
            return False
    
    def test_telegram(self) -> bool:
        """Test 5: Telegram (nur wenn konfiguriert)"""
        self.log("\n📱 Test 5: Telegram", "info")
        
        notifier = TelegramNotifier()
        
        if not notifier.is_configured():
            self.log("⚠️  Telegram nicht konfiguriert - überspringe (OK)", "warning")
            return True
        
        try:
            # Versuche Test-Nachricht (nur Dry-Run)
            result = notifier.sync_send_alert([])
            
            self.check("Telegram konfiguriert", notifier.is_configured())
            self.check("Telegram Test sendbar", result is not None)
            
            return True
            
        except Exception as e:
            self.check("Telegram-Test", False, str(e))
            return False
    
    def test_docker(self) -> bool:
        """Test 6: Docker verfügbar"""
        self.log("\n🐳 Test 6: Docker", "info")
        
        docker_available = os.system("docker --version > /dev/null 2>&1") == 0
        docker_compose_available = os.system("docker-compose --version > /dev/null 2>&1") == 0
        
        checks = [
            self.check("Docker installiert", docker_available),
            self.check("Docker Compose verfügbar", docker_compose_available),
        ]
        
        if docker_available:
            # Prüfe Dockerfile
            dockerfile_exists = Path("Dockerfile").exists()
            checks.append(self.check("Dockerfile existiert", dockerfile_exists))
        
        return all(checks)
    
    def run_all_tests(self) -> bool:
        """Führt alle Tests aus"""
        self.log("=" * 60, "info")
        self.log("🧪 Value-Bet Algorithm Test-Suite", "info")
        self.log("=" * 60, "info")
        
        tests = [
            ("Konfiguration", self.test_config),
            ("Modell", self.test_model),
            ("Scraper", self.test_scraper),
            ("Value Engine", self.test_value_engine),
            ("Telegram", self.test_telegram),
            ("Docker", self.test_docker),
        ]
        
        results = []
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
            except Exception as e:
                self.log(f"❌ {name} - CRASH: {e}", "error")
                results.append((name, False))
        
        # Summary
        self.log("\n" + "=" * 60, "info")
        self.log("📊 TEST-ZUSAMMENFASSUNG", "info")
        self.log("=" * 60, "info")
        
        for name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{name:20s} {status}", "success" if result else "error")
        
        total = len(results)
        passed = sum(1 for _, r in results if r)
        
        self.log(f"\nGesamt: {passed}/{total} Tests bestanden", 
                "success" if passed == total else "warning")
        
        if passed == total:
            self.log("\n🎉 Alle Tests erfolgreich! System bereit.", "success")
            self.log("\nNächster Schritt:", "info")
            self.log("  ./run.sh build    # Docker Image bauen", "info")
            self.log("  ./run.sh run      # Erster echter Test", "info")
        else:
            self.log("\n⚠️  Einige Tests fehlgeschlagen. Prüfe die Ausgabe.", "error")
        
        return passed == total


def main():
    """CLI Entry Point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test-Suite für Value-Bet Algorithm")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detaillierte Ausgabe")
    
    args = parser.parse_args()
    
    tester = DryRunTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
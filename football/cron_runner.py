#!/usr/bin/env python3
"""
Cron-Wrapper für automatisierte Value-Bet Checks
Wird regelmäßig ausgeführt (z.B. alle 30 Minuten)
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config
from historical_value import HistoricalValueAnalyzer
from notifications.telegram import TelegramNotifier


class CronRunner:
    """
    Automatisierter Runner für Cron/Scheduler
    Speichert Ergebnisse und History
    """
    
    def __init__(self):
        self.notifier = TelegramNotifier()
        self.results_dir = Path("data/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.results_dir / "history.json"
    
    def run_check(self, leagues: List[str] = None) -> dict:
        """
        Einzelner Check-Durchlauf
        """
        print(f"\n{'='*60}")
        print(f"[Cron] Starte Check: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print('='*60)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'leagues_checked': leagues or ['D1'],
            'value_bets_found': [],
            'alerts_sent': False,
            'errors': []
        }
        
        try:
            for league in (leagues or ['D1']):
                print(f"\n[Check] Liga: {league}")
                
                analyzer = HistoricalValueAnalyzer()
                value_bets = analyzer.analyze_current_fixtures(league)
                
                result['value_bets_found'].extend([
                    {
                        'home': vb.home_team,
                        'away': vb.away_team,
                        'bet': vb.bet_type,
                        'odds': vb.best_odds,
                        'value': vb.value_percentage,
                        'confidence': vb.confidence
                    }
                    for vb in value_bets
                ])
            
            # Filter auf High/Medium Confidence
            alert_bets = [vb for vb in result['value_bets_found'] 
                         if vb.get('confidence') in ['high', 'medium']]
            
            # Sende Telegram wenn konfiguriert und Value gefunden
            if self.notifier.is_configured() and alert_bets:
                print(f"[Cron] Sende {len(alert_bets)} Alerts via Telegram...")
                
                # Rekonstruiere ValueBet Objekte für Telegram
                from engine.value_engine import ValueBet
                bet_objects = []
                for bet_data in alert_bets[:5]:  # Max 5
                    bet = ValueBet(
                        home_team=bet_data['home'],
                        away_team=bet_data['away'],
                        league=result['leagues_checked'][0],
                        match_datetime=datetime.now(),
                        bet_type=bet_data['bet'],
                        selection=bet_data['home'] if bet_data['bet'] == '1' else (bet_data['away'] if bet_data['bet'] == '2' else 'Draw'),
                        model_probability=0.5,  # Simplified
                        market_probability=1/bet_data['odds'],
                        best_odds=bet_data['odds'],
                        bookmaker='bet365',
                        value_percentage=bet_data['value'],
                        expected_value=bet_data['value'] * bet_data['odds'],
                        kelly_stake=10.0,
                        confidence=bet_data['confidence']
                    )
                    bet_objects.append(bet)
                
                success = self.notifier.sync_send_alert(bet_objects)
                result['alerts_sent'] = success
                
                if success:
                    print("[Cron] ✅ Alerts gesendet!")
                else:
                    print("[Cron] ❌ Alert-Fehler")
            
            # Speichere History
            self._save_history(result)
            
        except Exception as e:
            print(f"[Cron] ❌ Error: {e}")
            result['errors'].append(str(e))
        
        return result
    
    def _save_history(self, result: dict):
        """Speichert Ergebnis in History"""
        history = []
        if self.history_file.exists():
            with open(self.history_file) as f:
                history = json.load(f)
        
        history.append(result)
        
        # Max 100 Einträge
        history = history[-100:]
        
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2, default=str)
    
    def get_stats(self) -> dict:
        """Zeigt Statistiken der letzten Checks"""
        if not self.history_file.exists():
            return {'checks': 0, 'total_bets': 0}
        
        with open(self.history_file) as f:
            history = json.load(f)
        
        total_checks = len(history)
        total_bets = sum(len(h.get('value_bets_found', [])) for h in history)
        alerts_sent = sum(1 for h in history if h.get('alerts_sent'))
        
        return {
            'checks': total_checks,
            'total_bets': total_bets,
            'alerts_sent': alerts_sent,
            'last_check': history[-1]['timestamp'] if history else None
        }


def main():
    """CLI für Cron-Ausführung"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cron Runner für Value-Bet Checks")
    parser.add_argument("--leagues", nargs="+", default=["D1"], help="Zu checkende Ligen (D1 D2 E0 SP1 I1 F1 P1 N1)")
    parser.add_argument("--stats", action="store_true", help="Zeige Statistiken")
    
    args = parser.parse_args()
    
    runner = CronRunner()
    
    if args.stats:
        stats = runner.get_stats()
        print(f"\n📊 Cron Statistiken:")
        print(f"   Checks: {stats['checks']}")
        print(f"   Total Bets: {stats['total_bets']}")
        print(f"   Alerts: {stats['alerts_sent']}")
        print(f"   Last: {stats['last_check']}")
        return
    
    # Normaler Check
    result = runner.run_check(args.leagues)
    
    print(f"\n{'='*60}")
    print(f"[Cron] Ergebnis:")
    print(f"   Value-Bets: {len(result['value_bets_found'])}")
    print(f"   Alerts: {'✅' if result['alerts_sent'] else '❌'}")
    print(f"   Errors: {len(result['errors'])}")


if __name__ == "__main__":
    main()
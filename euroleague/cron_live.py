#!/usr/bin/env python3
"""EuroLeague live runner with tracking, risk, calibration, and closing-line snapshots."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent / 'src') not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from shared.calibration import MarketCalibration
from shared.closing_line import ClosingLineManager
from shared.feedback_loop import UniversalBetTracker
from shared.model_registry import ModelRegistry
from shared.risk_manager import PortfolioRiskManager
from shared.runtime_utils import canonical_event_key, load_env, now_iso
from config import DATA_DIR, MODELS_DIR
from hybrid_model import EuroleagueHybridModel
from odds_scraper import EuroleagueOddsScraper
from value_engine import NBAValueEngine

load_env()

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'football' / 'src'))
    from notifications.telegram import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False
    TelegramNotifier = None


class EuroleagueCronRunner:
    def __init__(self, execution_mode: str = 'live'):
        self.execution_mode = execution_mode
        self.scraper = EuroleagueOddsScraper()
        self.tracker = UniversalBetTracker()
        self.calibration = MarketCalibration()
        self.closing = ClosingLineManager()
        self.registry = ModelRegistry()
        self.risk = PortfolioRiskManager(bankroll=1000.0)
        self.notifier = TelegramNotifier() if TELEGRAM_AVAILABLE else None
        self.model_path = MODELS_DIR / 'euroleague_hybrid.json'
        self.model = EuroleagueHybridModel.load(self.model_path)
        self.registry.ensure_registered_from_file('euroleague', self.model_path) if self.model_path.exists() else None

    def _record_snapshots(self, game: dict):
        rows = []
        for option in game.get('home_odds_options', []):
            rows.append({'market': 'moneyline', 'selection': game['home_team'], 'bookmaker': option['bookmaker'], 'odds': option['odds']})
        for option in game.get('away_odds_options', []):
            rows.append({'market': 'moneyline', 'selection': game['away_team'], 'bookmaker': option['bookmaker'], 'odds': option['odds']})
        for option in game.get('home_spread_options', []):
            rows.append({'market': 'spread', 'selection': f"{game['home_team']} {float(game.get('spread') or 0):+.1f}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        for option in game.get('away_spread_options', []):
            rows.append({'market': 'spread', 'selection': f"{game['away_team']} {-float(game.get('spread') or 0):+.1f}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        for option in game.get('over_odds_options', []):
            rows.append({'market': 'totals', 'selection': f"Over {game.get('total_line')}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        for option in game.get('under_odds_options', []):
            rows.append({'market': 'totals', 'selection': f"Under {game.get('total_line')}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        self.closing.record_candidates('euroleague', game['home_team'], game['away_team'], game.get('commence_time'), game.get('game_id', ''), rows)

    def run(self):
        odds = self.scraper.fetch_upcoming()
        if odds.empty:
            return {'timestamp': now_iso(), 'execution_mode': self.execution_mode, 'bets_tracked': 0, 'alerts_sent': 0, 'games': 0}
        active_cache = self.tracker.get_active_bets(sport='euroleague')
        perf = self.tracker.calculate_performance(days=90, sport='euroleague', execution_mode=self.execution_mode)
        engine = NBAValueEngine(value_threshold=0.035, kelly_fraction=0.20, historical_performance=perf)
        alerts = []
        tracked_count = 0
        for _, game in odds.iterrows():
            game = game.to_dict()
            self._record_snapshots(game)
            preds = self.model.predict(game['home_team'], game['away_team'], game.get('home_odds'), game.get('away_odds'))
            preds['home_cover_prob'] = self.model.predict_spread_cover(game['home_team'], game['away_team'], game.get('spread') or 0.0, game.get('home_odds'), game.get('away_odds'))
            preds['over_prob'] = self.model.predict_total(game.get('total_line') or 160.5, game.get('over_odds'), game.get('under_odds'))
            bets = engine.analyze_game(game['game_id'], game['home_team'], game['away_team'], {
                'home_odds': game.get('home_odds'), 'away_odds': game.get('away_odds'),
                'home_spread': game.get('spread') or 0.0, 'home_spread_odds': game.get('home_spread_odds'), 'away_spread_odds': game.get('away_spread_odds'),
                'over_line': game.get('total_line') or 160.5, 'over_odds': game.get('over_odds'), 'under_odds': game.get('under_odds'),
            }, preds)
            for bet in bets:
                calibration = self.calibration.adjust_bet('euroleague', bet.market, bet.bet_size, bet.value, bet.confidence)
                payload = {
                    'execution_mode': self.execution_mode,
                    'sport': 'euroleague',
                    'league': 'EuroLeague',
                    'event_id': canonical_event_key('euroleague', game['home_team'], game['away_team'], game.get('commence_time')),
                    'match_id': game['game_id'],
                    'home_team': game['home_team'],
                    'away_team': game['away_team'],
                    'match_date': game.get('commence_time'),
                    'bet_type': bet.market,
                    'market': bet.market,
                    'selection': bet.selection,
                    'line': game.get('spread') if bet.market == 'spread' else game.get('total_line') if bet.market == 'totals' else None,
                    'odds': bet.odds,
                    'opening_odds': bet.odds,
                    'bookmaker': game.get('home_odds_bk') if bet.market == 'moneyline' and bet.selection == game['home_team'] else game.get('away_odds_bk') if bet.market == 'moneyline' else game.get('home_spread_bk') if bet.market == 'spread' and bet.selection.startswith(game['home_team']) else game.get('away_spread_bk') if bet.market == 'spread' else game.get('over_bk') if bet.selection.startswith('Over') else game.get('under_bk'),
                    'bookmaker_options': [],
                    'model_prob': bet.model_prob,
                    'market_prob': 1.0 / bet.odds if bet.odds and bet.odds > 1 else 0.0,
                    'value_percentage': bet.value,
                    'expected_value': bet.model_prob * bet.odds - 1.0 if bet.odds else 0.0,
                    'raw_kelly_stake': bet.bet_size,
                    'kelly_stake': calibration['adjusted_stake'],
                    'confidence': calibration['adjusted_confidence'],
                    'stake_multiplier': calibration['stake_multiplier'],
                    'calibration_version': self.calibration.profile.get('version', 'v3'),
                    'model_version': 'euroleague-hybrid-v1',
                    'feature_set_version': 'v3.known-sports',
                    'data_version': 'v3.known-sports',
                    'thresholds_version': 'v3.known-sports',
                    'odds_timestamp': bet.odds_timestamp or now_iso(),
                }
                risk = self.risk.evaluate_bet(payload, active_cache)
                if not risk.approved:
                    continue
                payload['kelly_stake'] = risk.approved_stake
                payload['risk_status'] = risk.status
                payload['risk_reasons'] = risk.reasons
                payload['stake_multiplier'] = round(payload['stake_multiplier'] * risk.stake_multiplier, 3)
                if (payload['event_id'], payload['market'], payload['selection']) in {(b.get('event_id'), b.get('market'), b.get('selection')) for b in active_cache}:
                    continue
                self.tracker.place_bet(payload, sport='euroleague')
                active_cache.append(payload)
                tracked_count += 1
                if payload['confidence'] in ('high', 'medium'):
                    alerts.append(bet)
        if alerts and self.execution_mode == 'live' and self.notifier and self.notifier.is_configured():
            try:
                self.notifier.sync_send_nba_alert({
                    'selection': alerts[0].selection,
                    'market': alerts[0].market,
                    'odds': alerts[0].odds,
                    'value': alerts[0].value,
                    'bet_size': alerts[0].bet_size,
                    'confidence': alerts[0].confidence,
                })
            except Exception:
                pass
        return {'timestamp': now_iso(), 'execution_mode': self.execution_mode, 'bets_tracked': tracked_count, 'alerts_sent': min(len(alerts), 1), 'games': int(len(odds))}


def main():
    parser = argparse.ArgumentParser(description='EuroLeague live runner')
    parser.add_argument('--execution-mode', choices=['live', 'shadow'], default='live')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = EuroleagueCronRunner(execution_mode=args.execution_mode).run()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"EuroLeague games={result['games']} bets={result['bets_tracked']} alerts={result['alerts_sent']}")


if __name__ == '__main__':
    main()

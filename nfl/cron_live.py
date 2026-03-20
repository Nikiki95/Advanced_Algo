#!/usr/bin/env python3
"""NFL live runner V3 with line shopping, risk controls, and versioned tracking."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent / 'src') not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from shared.calibration import MarketCalibration
from shared.closing_line import ClosingLineManager
from shared.data_quality import dedupe_games, validate_dataframe
from shared.feedback_loop import UniversalBetTracker
from shared.model_registry import ModelRegistry
from shared.risk_manager import PortfolioRiskManager
from shared.runtime_utils import canonical_event_key, load_env, now_iso
from config import MODELS_DIR
from power_rank_model import NFLPowerModel
from odds_scraper import NFLOddsScraper
from value_engine import NFLValueEngine

load_env()

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'football' / 'src'))
    from notifications.telegram import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False
    TelegramNotifier = None


class NFLCronRunner:
    def __init__(self, execution_mode: str = 'live'):
        self.execution_mode = execution_mode
        self.scraper = NFLOddsScraper()
        self.tracker = UniversalBetTracker()
        self.calibration = MarketCalibration()
        self.closing = ClosingLineManager()
        self.registry = ModelRegistry()
        self.risk = PortfolioRiskManager(bankroll=1000.0)
        self.notifier = TelegramNotifier() if TELEGRAM_AVAILABLE else None
        self.model = None
        self.model_path = None
        self._load_model()

    def _load_model(self):
        active = self.registry.get_active('nfl')
        candidate_path = Path(active['file_path']) if active and Path(active['file_path']).exists() else None
        if not candidate_path:
            files = sorted(MODELS_DIR.glob('nfl_power_*.pkl'), key=lambda p: p.stat().st_mtime)
            candidate_path = files[-1] if files else None
        if candidate_path:
            self.model = NFLPowerModel.load(str(candidate_path))
            self.model_path = candidate_path
            self.registry.ensure_registered_from_file('nfl', candidate_path)

    def _record_snapshots(self, game: dict):
        rows = []
        for option in game.get('home_odds_options', []):
            rows.append({'market': 'moneyline', 'selection': game['home_team'], 'bookmaker': option['bookmaker'], 'odds': option['odds']})
        for option in game.get('away_odds_options', []):
            rows.append({'market': 'moneyline', 'selection': game['away_team'], 'bookmaker': option['bookmaker'], 'odds': option['odds']})
        for option in game.get('home_spread_options', []):
            rows.append({'market': 'spread', 'selection': f"{game['home_team']} {float(game.get('spread', 0)):+.1f}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        for option in game.get('away_spread_options', []):
            rows.append({'market': 'spread', 'selection': f"{game['away_team']} {-float(game.get('spread', 0)):+.1f}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        for option in game.get('over_odds_options', []):
            rows.append({'market': 'totals', 'selection': f"Over {game.get('total_line')}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        for option in game.get('under_odds_options', []):
            rows.append({'market': 'totals', 'selection': f"Under {game.get('total_line')}", 'bookmaker': option['bookmaker'], 'odds': option['odds'], 'line': option.get('line')})
        self.closing.record_candidates('nfl', game['home_team'], game['away_team'], game.get('commence_time'), game.get('game_id', ''), rows)

    def run(self):
        if not self.model:
            return {'error': 'no_model'}
        odds = dedupe_games(self.scraper.fetch_upcoming())
        issues = validate_dataframe(odds, required_cols=['home_team', 'away_team'], odds_cols=['home_odds', 'away_odds', 'home_spread_odds', 'away_spread_odds', 'over_odds', 'under_odds']) if not odds.empty else []
        active_cache = self.tracker.get_active_bets(sport='nfl')
        engine = NFLValueEngine(historical_performance=self.tracker.calculate_performance(days=120, sport='nfl', execution_mode=self.execution_mode))
        tracked, alert_payloads = [], []
        for _, game in odds.iterrows():
            game = game.to_dict()
            self._record_snapshots(game)
            preds = self.model.predict_spread(game['home_team'], game['away_team'])
            total_pred = self.model.predict_total(game['home_team'], game['away_team'], line=float(game.get('total_line') or 45.0))
            bets = engine.analyze_game(game['game_id'], game['home_team'], game['away_team'], game, {'home_win_prob': preds['home_win_prob'], 'home_cover_prob': preds['home_cover_prob'], 'over_prob': total_pred['over_prob']})
            for bet in bets:
                calibration = self.calibration.adjust_bet('nfl', bet.market, bet.bet_size, bet.value, bet.confidence)
                payload = {
                    'execution_mode': self.execution_mode,
                    'league': 'NFL', 'match_id': game['game_id'],
                    'event_id': canonical_event_key('nfl', game['home_team'], game['away_team'], game.get('commence_time')),
                    'home_team': game['home_team'], 'away_team': game['away_team'], 'match_date': game.get('commence_time'),
                    'bet_type': bet.market, 'market': bet.market, 'selection': bet.selection,
                    'line': game.get('spread') if bet.market == 'spread' else game.get('total_line'),
                    'odds': bet.odds, 'opening_odds': bet.odds,
                    'bookmaker': game.get('home_odds_bk') if bet.market == 'moneyline' and bet.selection == game['home_team'] else game.get('away_odds_bk') if bet.market == 'moneyline' else game.get('home_spread_bk') if bet.market == 'spread' and bet.selection.startswith(game['home_team']) else game.get('away_spread_bk') if bet.market == 'spread' else game.get('over_bk') if bet.selection.startswith('Over') else game.get('under_bk'),
                    'bookmaker_options': game.get('home_odds_options') if bet.market == 'moneyline' and bet.selection == game['home_team'] else game.get('away_odds_options') if bet.market == 'moneyline' else game.get('home_spread_options') if bet.market == 'spread' and bet.selection.startswith(game['home_team']) else game.get('away_spread_options') if bet.market == 'spread' else game.get('over_odds_options') if bet.selection.startswith('Over') else game.get('under_odds_options'),
                    'model_prob': bet.model_prob, 'market_prob': 1 / bet.odds if bet.odds > 1 else 0,
                    'value_percentage': bet.value, 'expected_value': bet.model_prob * bet.odds - 1,
                    'raw_kelly_stake': bet.bet_size, 'kelly_stake': calibration['adjusted_stake'],
                    'confidence': calibration['adjusted_confidence'], 'stake_multiplier': calibration['stake_multiplier'],
                    'model_version': self.model_path.stem if self.model_path else 'nfl-unversioned', 'feature_set_version': 'v3', 'data_version': 'v3', 'thresholds_version': 'v3',
                    'calibration_version': self.calibration.profile.get('version', 'v3'), 'odds_timestamp': bet.odds_timestamp or now_iso(),
                }
                dedupe_key = (payload['event_id'], payload['market'], payload['selection'])
                if dedupe_key in {(b.get('event_id'), b.get('market'), b.get('selection')) for b in active_cache}:
                    continue
                risk = self.risk.evaluate_bet({'sport': 'nfl', **payload}, active_cache)
                if not risk.approved:
                    continue
                payload['risk_status'] = risk.status
                payload['risk_reasons'] = risk.reasons
                payload['kelly_stake'] = risk.approved_stake
                self.tracker.place_bet(payload, sport='nfl')
                active_cache.append({'sport': 'nfl', **payload})
                tracked.append(payload)
                if payload['confidence'] in ('high', 'medium'):
                    alert_payloads.append({'match': f"{game['home_team']} vs {game['away_team']}", 'market': bet.market, 'selection': bet.selection, 'odds': bet.odds, 'value': bet.value, 'bet_size': payload['kelly_stake'], 'confidence': payload['confidence']})
        if self.execution_mode == 'live' and alert_payloads and self.notifier and self.notifier.is_configured():
            for alert in alert_payloads[:5]:
                self.notifier.sync_send_nfl_alert(alert)
        result = {'timestamp': now_iso(), 'execution_mode': self.execution_mode, 'bets_tracked': len(tracked), 'issues': [i.message for i in issues], 'alerts': min(5, len(alert_payloads))}
        print(json.dumps(result, indent=2))
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shadow', action='store_true')
    args = parser.parse_args()
    runner = NFLCronRunner(execution_mode='shadow' if args.shadow else os.getenv('EXECUTION_MODE', 'live'))
    runner.run()


if __name__ == '__main__':
    main()

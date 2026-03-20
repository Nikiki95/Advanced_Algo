#!/usr/bin/env python3
"""Tennis live runner focused on tournament-based match-winner markets."""
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
from config import MODELS_DIR, TOURNAMENTS
from hybrid_model import TennisHybridModel
from odds_scraper import TennisOddsScraper
from value_engine import TennisValueEngine

load_env()


class TennisCronRunner:
    def __init__(self, execution_mode: str = 'live'):
        self.execution_mode = execution_mode
        self.scraper = TennisOddsScraper()
        self.tracker = UniversalBetTracker()
        self.calibration = MarketCalibration()
        self.closing = ClosingLineManager()
        self.registry = ModelRegistry()
        self.risk = PortfolioRiskManager(bankroll=1000.0)
        self.model_path = MODELS_DIR / 'player_ratings.json'
        self.model = TennisHybridModel.load(self.model_path)
        self.registry.ensure_registered_from_file('tennis', self.model_path) if self.model_path.exists() else None

    def _record_snapshots(self, row: dict):
        rows = []
        for option in row.get('home_odds_options', []):
            rows.append({'market': 'moneyline', 'selection': row['home_player'], 'bookmaker': option['bookmaker'], 'odds': option['odds']})
        for option in row.get('away_odds_options', []):
            rows.append({'market': 'moneyline', 'selection': row['away_player'], 'bookmaker': option['bookmaker'], 'odds': option['odds']})
        self.closing.record_candidates('tennis', row['home_player'], row['away_player'], row.get('commence_time'), row.get('match_id', ''), rows)

    def run(self, tournaments: list[str]):
        engine = TennisValueEngine()
        active_cache = self.tracker.get_active_bets(sport='tennis')
        tracked = 0
        matches = 0
        for alias in tournaments:
            key = TOURNAMENTS.get(alias, alias)
            df = self.scraper.fetch_tournament(key)
            if df.empty:
                continue
            for _, row in df.iterrows():
                row = row.to_dict()
                matches += 1
                self._record_snapshots(row)
                preds = self.model.predict(row['home_player'], row['away_player'], row.get('home_odds'), row.get('away_odds'), row['tournament_key'])
                bets = engine.evaluate(row['match_id'], row['home_player'], row['away_player'], row.get('home_odds'), row.get('away_odds'), preds['player_one_prob'])
                for bet in bets:
                    calibration = self.calibration.adjust_bet('tennis', 'moneyline', bet.bet_size, bet.value, bet.confidence)
                    payload = {
                        'execution_mode': self.execution_mode,
                        'sport': 'tennis',
                        'league': row['tournament_key'],
                        'event_id': canonical_event_key('tennis', row['home_player'], row['away_player'], row.get('commence_time')),
                        'match_id': row['match_id'],
                        'home_team': row['home_player'],
                        'away_team': row['away_player'],
                        'match_date': row.get('commence_time'),
                        'bet_type': 'moneyline',
                        'market': 'moneyline',
                        'selection': bet.selection,
                        'line': None,
                        'odds': bet.odds,
                        'opening_odds': bet.odds,
                        'bookmaker': row.get('home_odds_bk') if bet.selection == row['home_player'] else row.get('away_odds_bk'),
                        'bookmaker_options': row.get('home_odds_options') if bet.selection == row['home_player'] else row.get('away_odds_options'),
                        'model_prob': bet.model_prob,
                        'market_prob': 1.0 / bet.odds if bet.odds and bet.odds > 1 else 0.0,
                        'value_percentage': bet.value,
                        'expected_value': bet.model_prob * bet.odds - 1.0,
                        'raw_kelly_stake': bet.bet_size,
                        'kelly_stake': calibration['adjusted_stake'],
                        'confidence': calibration['adjusted_confidence'],
                        'stake_multiplier': calibration['stake_multiplier'],
                        'calibration_version': self.calibration.profile.get('version', 'v3'),
                        'model_version': 'tennis-hybrid-v1',
                        'feature_set_version': 'v3.known-sports',
                        'data_version': 'v3.known-sports',
                        'thresholds_version': 'v3.known-sports',
                        'odds_timestamp': bet.odds_timestamp or now_iso(),
                    }
                    if (payload['event_id'], payload['market'], payload['selection']) in {(b.get('event_id'), b.get('market'), b.get('selection')) for b in active_cache}:
                        continue
                    risk = self.risk.evaluate_bet(payload, active_cache)
                    if not risk.approved:
                        continue
                    payload['kelly_stake'] = risk.approved_stake
                    payload['risk_status'] = risk.status
                    payload['risk_reasons'] = risk.reasons
                    payload['stake_multiplier'] = round(payload['stake_multiplier'] * risk.stake_multiplier, 3)
                    self.tracker.place_bet(payload, sport='tennis')
                    active_cache.append(payload)
                    tracked += 1
        return {'timestamp': now_iso(), 'execution_mode': self.execution_mode, 'bets_tracked': tracked, 'matches': matches, 'tournaments': tournaments}


def main():
    parser = argparse.ArgumentParser(description='Tennis live runner')
    parser.add_argument('--execution-mode', choices=['live', 'shadow'], default='live')
    parser.add_argument('--tournaments', nargs='+', default=['atp_indian_wells', 'atp_miami', 'wta_indian_wells', 'wta_miami'])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = TennisCronRunner(execution_mode=args.execution_mode).run(args.tournaments)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Tennis tournaments={len(result['tournaments'])} matches={result['matches']} bets={result['bets_tracked']}")


if __name__ == '__main__':
    main()

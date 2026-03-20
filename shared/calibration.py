"""Market-specific calibration and stake-adjustment profiles."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .runtime_utils import data_root, ensure_parent, now_iso


class MarketCalibration:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_root() / 'calibration' / 'market_calibration.json'
        self.profile = self.load()

    def load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                pass
        return {'updated_at': None, 'markets': {}, 'version': 'v3'}

    def save(self, profile: Dict):
        ensure_parent(self.path)
        self.path.write_text(json.dumps(profile, indent=2), encoding='utf-8')
        self.profile = profile

    def market_key(self, sport: str, market: str) -> str:
        return f"{sport}:{market}"

    def generate(self, settled_bets: List[Dict], min_samples: int = 12) -> Dict:
        grouped = defaultdict(list)
        for bet in settled_bets:
            sport = bet.get('sport', 'unknown')
            market = bet.get('market') or bet.get('bet_type') or 'unknown'
            grouped[self.market_key(sport, market)].append(bet)

        markets = {}
        for key, bets in grouped.items():
            graded = [b for b in bets if b.get('actual_result') in ('win', 'loss')]
            if len(graded) < min_samples:
                continue
            wins = sum(1 for b in graded if b.get('actual_result') == 'win')
            observed = wins / len(graded)
            avg_model = sum(float(b.get('model_prob') or 0) for b in graded) / len(graded)
            avg_roi = sum(float(b.get('profit_loss') or 0) for b in graded) / max(1, sum(float(b.get('kelly_stake') or 0) for b in graded))
            gap = observed - avg_model
            if gap < -0.05:
                threshold_mult = 1.15
                stake_mult = 0.80
            elif gap < -0.02:
                threshold_mult = 1.08
                stake_mult = 0.90
            elif gap > 0.03:
                threshold_mult = 0.96
                stake_mult = 1.05
            else:
                threshold_mult = 1.00
                stake_mult = 1.00
            markets[key] = {
                'sample_size': len(graded),
                'observed_win_rate': round(observed, 4),
                'avg_model_prob': round(avg_model, 4),
                'calibration_gap': round(gap, 4),
                'roi': round(avg_roi, 4),
                'threshold_multiplier': threshold_mult,
                'stake_multiplier': stake_mult,
            }

        profile = {'updated_at': now_iso(), 'markets': markets, 'version': 'v3'}
        self.save(profile)
        return profile

    def get_market_adjustment(self, sport: str, market: str) -> Dict:
        key = self.market_key(sport, market)
        return self.profile.get('markets', {}).get(key, {
            'sample_size': 0,
            'threshold_multiplier': 1.0,
            'stake_multiplier': 1.0,
            'calibration_gap': 0.0,
        })

    def adjust_bet(self, sport: str, market: str, stake: float, value: float, confidence: str) -> Dict:
        adj = self.get_market_adjustment(sport, market)
        threshold_mult = float(adj.get('threshold_multiplier', 1.0))
        stake_mult = float(adj.get('stake_multiplier', 1.0))
        adjusted_stake = stake * stake_mult
        adjusted_conf = confidence
        if threshold_mult >= 1.12 and confidence == 'high':
            adjusted_conf = 'medium'
        elif threshold_mult >= 1.12 and confidence == 'medium':
            adjusted_conf = 'low'
        elif threshold_mult <= 0.97 and confidence == 'medium' and value >= 0.07:
            adjusted_conf = 'high'
        return {
            'threshold_multiplier': threshold_mult,
            'stake_multiplier': stake_mult,
            'adjusted_stake': round(adjusted_stake, 2),
            'adjusted_confidence': adjusted_conf,
            'calibration_gap': adj.get('calibration_gap', 0.0),
            'sample_size': adj.get('sample_size', 0),
        }

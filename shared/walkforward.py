"""Lightweight threshold tuning over historical tracked bets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .runtime_utils import data_root, ensure_parent, now_iso


class WalkForwardOptimizer:
    def __init__(self, out_path: Optional[Path] = None):
        self.out_path = out_path or data_root() / 'optimization' / 'walkforward_summary.json'

    def optimize_thresholds(self, settled_bets: List[Dict], sport: Optional[str] = None) -> Dict:
        bets = [b for b in settled_bets if b.get('actual_result') in ('win', 'loss')]
        if sport:
            bets = [b for b in bets if b.get('sport') == sport]
        thresholds = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08]
        results = []
        for threshold in thresholds:
            subset = [b for b in bets if float(b.get('value_percentage') or 0) >= threshold]
            staked = sum(float(b.get('kelly_stake') or 0) for b in subset)
            profit = sum(float(b.get('profit_loss') or 0) for b in subset)
            roi = (profit / staked * 100) if staked > 0 else 0.0
            results.append({
                'threshold': threshold,
                'bets': len(subset),
                'profit': round(profit, 2),
                'roi_percent': round(roi, 2),
            })
        best = max(results, key=lambda x: (x['roi_percent'], x['bets'])) if results else None
        summary = {'updated_at': now_iso(), 'sport': sport or 'all', 'results': results, 'best': best}
        ensure_parent(self.out_path)
        self.out_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
        return summary

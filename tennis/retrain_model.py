#!/usr/bin/env python3
"""Simple tennis retraining wrapper using settled moneyline bets as rating signals."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent / 'src') not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from shared.feedback_loop import UniversalBetTracker
from config import MODELS_DIR
from hybrid_model import TennisHybridModel


def main():
    tracker = UniversalBetTracker()
    bets = tracker.get_settled_bets(days=365, sport='tennis')
    ratings = {}
    k = 14.0
    for bet in bets:
        if str(bet.get('market')) not in ('moneyline', 'h2h'):
            continue
        p1 = bet.get('home_team')
        p2 = bet.get('away_team')
        if not p1 or not p2:
            continue
        r1 = ratings.get(p1, 1500.0)
        r2 = ratings.get(p2, 1500.0)
        expected = 1.0 / (1.0 + 10 ** ((r2 - r1) / 400.0))
        winner = None
        selection = str(bet.get('selection') or '')
        if bet.get('actual_result') == 'win':
            winner = p1 if selection == p1 else p2
        elif bet.get('actual_result') == 'loss':
            winner = p2 if selection == p1 else p1
        if winner is None:
            continue
        actual = 1.0 if winner == p1 else 0.0
        delta = k * (actual - expected)
        ratings[p1] = r1 + delta
        ratings[p2] = r2 - delta
    model = TennisHybridModel(ratings=ratings)
    out = MODELS_DIR / 'player_ratings.json'
    model.save(out)
    print(json.dumps({'model_path': str(out), 'players': len(ratings)}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Simple EuroLeague retraining wrapper using settled results to refresh team ratings."""
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
from config import MODELS_DIR, HOME_ADVANTAGE_ELO
from hybrid_model import EuroleagueHybridModel


def main():
    tracker = UniversalBetTracker()
    bets = tracker.get_settled_bets(days=365, sport='euroleague')
    ratings = {}
    k = 16.0
    for bet in bets:
        if str(bet.get('market')) != 'moneyline':
            continue
        home = bet.get('home_team')
        away = bet.get('away_team')
        if not home or not away:
            continue
        home_rating = ratings.get(home, 1500.0)
        away_rating = ratings.get(away, 1500.0)
        expected = 1.0 / (1.0 + 10 ** ((away_rating - (home_rating + HOME_ADVANTAGE_ELO)) / 400.0))
        winner = bet.get('winner') or ('home' if bet.get('actual_result') == 'win' and bet.get('selection') == home else 'away' if bet.get('actual_result') == 'win' else None)
        if winner is None:
            continue
        actual = 1.0 if winner == 'home' else 0.0
        delta = k * (actual - expected)
        ratings[home] = home_rating + delta
        ratings[away] = away_rating - delta
    model = EuroleagueHybridModel(ratings=ratings, home_advantage_elo=HOME_ADVANTAGE_ELO)
    out = MODELS_DIR / 'euroleague_hybrid.json'
    model.save(out)
    print(json.dumps({'model_path': str(out), 'teams': len(ratings)}))


if __name__ == '__main__':
    main()

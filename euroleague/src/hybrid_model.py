"""Consensus + optional rating model for EuroLeague."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterable, Optional


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def devig_two_way(home_odds: float, away_odds: float) -> tuple[float, float]:
    if not home_odds or not away_odds or home_odds <= 1 or away_odds <= 1:
        return 0.5, 0.5
    p1 = 1.0 / home_odds
    p2 = 1.0 / away_odds
    total = p1 + p2
    if total <= 0:
        return 0.5, 0.5
    return p1 / total, p2 / total


class EuroleagueHybridModel:
    def __init__(self, ratings: Optional[Dict[str, float]] = None, home_advantage_elo: float = 70.0):
        self.ratings = ratings or {}
        self.home_advantage_elo = home_advantage_elo

    @classmethod
    def load(cls, path: str | Path):
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding='utf-8'))
        return cls(ratings=data.get('ratings', {}), home_advantage_elo=float(data.get('home_advantage_elo', 70.0)))

    def save(self, path: str | Path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({'ratings': self.ratings, 'home_advantage_elo': self.home_advantage_elo}, indent=2), encoding='utf-8')

    def get_rating(self, team: str) -> float:
        return float(self.ratings.get(team, 1500.0))

    def predict(self, home_team: str, away_team: str, home_odds: float, away_odds: float) -> Dict:
        market_home, market_away = devig_two_way(home_odds, away_odds)
        rating_diff = (self.get_rating(home_team) - self.get_rating(away_team) + self.home_advantage_elo) / 400.0
        rating_home = logistic(rating_diff)
        # blend market and rating signal, market gets stronger weight for robustness
        home_win_prob = 0.65 * market_home + 0.35 * rating_home
        return {
            'home_win_prob': home_win_prob,
            'away_win_prob': 1.0 - home_win_prob,
            'market_home_prob': market_home,
            'rating_home_prob': rating_home,
        }

    def predict_spread_cover(self, home_team: str, away_team: str, spread: float, home_odds: float, away_odds: float) -> float:
        base = self.predict(home_team, away_team, home_odds, away_odds)['home_win_prob']
        expected_margin = (base - 0.5) / 0.028
        std_dev = 11.0
        z = (expected_margin + float(spread or 0.0)) / std_dev
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    def predict_total(self, total_line: float, over_odds: float, under_odds: float) -> float:
        if not over_odds or not under_odds:
            return 0.5
        market_over, _ = devig_two_way(over_odds, under_odds)
        return market_over

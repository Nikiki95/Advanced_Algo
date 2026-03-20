"""Consensus-driven tennis model with optional local player ratings."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Optional


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


class TennisHybridModel:
    def __init__(self, ratings: Optional[Dict[str, float]] = None, surfaces: Optional[Dict[str, Dict[str, float]]] = None):
        self.ratings = ratings or {}
        self.surfaces = surfaces or {}

    @classmethod
    def load(cls, path: str | Path):
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding='utf-8'))
        return cls(ratings=data.get('ratings', {}), surfaces=data.get('surfaces', {}))

    def save(self, path: str | Path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({'ratings': self.ratings, 'surfaces': self.surfaces}, indent=2), encoding='utf-8')

    def get_rating(self, player: str) -> float:
        return float(self.ratings.get(player, 1500.0))

    def surface_adjustment(self, player: str, tournament_key: str) -> float:
        surface = 'hard'
        if 'wimbledon' in tournament_key:
            surface = 'grass'
        elif any(x in tournament_key for x in ('madrid', 'italian_open', 'french_open', 'monte_carlo')):
            surface = 'clay'
        return float(self.surfaces.get(player, {}).get(surface, 0.0))

    def predict(self, player_one: str, player_two: str, odds_one: float, odds_two: float, tournament_key: str) -> Dict:
        market_one, market_two = devig_two_way(odds_one, odds_two)
        rating_delta = (self.get_rating(player_one) - self.get_rating(player_two)) / 180.0
        surface_delta = (self.surface_adjustment(player_one, tournament_key) - self.surface_adjustment(player_two, tournament_key)) / 100.0
        rating_one = logistic(rating_delta + surface_delta)
        player_one_prob = 0.70 * market_one + 0.30 * rating_one
        return {
            'player_one_prob': player_one_prob,
            'player_two_prob': 1.0 - player_one_prob,
            'market_player_one_prob': market_one,
            'rating_player_one_prob': rating_one,
        }

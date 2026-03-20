"""Simple tennis H2H value engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class TennisValueBet:
    match_id: str
    market: str
    selection: str
    odds: float
    model_prob: float
    value: float
    kelly: float
    bet_size: float
    confidence: str
    odds_timestamp: Optional[str] = None


class TennisValueEngine:
    def __init__(self, value_threshold: float = 0.035, kelly_fraction: float = 0.15, bankroll: float = 1000.0):
        self.value_threshold = value_threshold
        self.kelly_fraction = kelly_fraction
        self.bankroll = bankroll
        self.thresholds = {'high': 0.09, 'medium': 0.05, 'low': value_threshold}

    def implied_prob(self, odds: float) -> float:
        return 1.0 / odds if odds and odds > 1 else 0.0

    def kelly(self, prob: float, odds: float) -> float:
        if odds <= 1.0:
            return 0.0
        b = odds - 1.0
        raw = (b * prob - (1 - prob)) / b
        return max(0.0, min(1.0, raw))

    def confidence(self, edge: float) -> str:
        if edge >= self.thresholds['high']:
            return 'high'
        if edge >= self.thresholds['medium']:
            return 'medium'
        if edge >= self.thresholds['low']:
            return 'low'
        return 'none'

    def evaluate(self, match_id: str, player_one: str, player_two: str, odds_one: float, odds_two: float, player_one_prob: float) -> List[TennisValueBet]:
        bets = []
        now = datetime.utcnow().isoformat()
        for selection, odds, prob in [(player_one, odds_one, player_one_prob), (player_two, odds_two, 1.0 - player_one_prob)]:
            if not odds or odds <= 1.01:
                continue
            edge = prob - self.implied_prob(odds)
            if edge >= self.value_threshold:
                k = self.kelly(prob, odds)
                bets.append(TennisValueBet(match_id, 'moneyline', selection, odds, prob, edge, k, self.bankroll * k * self.kelly_fraction, self.confidence(edge), now))
        return bets

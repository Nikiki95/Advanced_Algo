"""
NFL Value Bet Engine v2
- Added totals (Over/Under) evaluation
- CLV tracking
- Bayesian confidence
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NFLValueBet:
    game_id: str
    market: str
    selection: str
    odds: float
    model_prob: float
    value: float
    kelly: float
    bet_size: float
    confidence: str
    odds_timestamp: Optional[str] = None
    closing_odds: Optional[float] = None
    clv: Optional[float] = None


class NFLValueEngine:
    """NFL Value Engine v2 — Spread + Moneyline + Totals."""

    def __init__(self,
                 value_threshold: float = 0.04,
                 kelly_fraction: float = 0.25,
                 min_odds: float = 1.25,
                 max_odds: float = 8.0,
                 bankroll: float = 1000.0,
                 historical_performance: Optional[Dict] = None):
        self.value_threshold = value_threshold
        self.kelly_fraction = kelly_fraction
        self.min_odds = min_odds
        self.max_odds = max_odds
        self.bankroll = bankroll

        self._thresholds = {'high': 0.08, 'medium': 0.04, 'low': 0.02}
        if historical_performance:
            self._calibrate(historical_performance)

    def _calibrate(self, perf: Dict):
        total = perf.get('total_bets', 0)
        if total < 15:
            return
        roi = perf.get('roi_percent', 0)
        if roi < -5:
            for k in self._thresholds:
                self._thresholds[k] *= 1.15
        elif roi > 8:
            for k in self._thresholds:
                self._thresholds[k] *= 0.92

    def implied_prob(self, odds: float) -> float:
        return 1.0 / odds if odds > 1.0 else 0.0

    def edge(self, model_prob: float, odds: float) -> float:
        return model_prob - self.implied_prob(odds)

    def kelly(self, prob: float, odds: float) -> float:
        if odds <= 1.0 or prob <= 0:
            return 0.0
        b = odds - 1.0
        k = (b * prob - (1 - prob)) / b
        return max(0.0, min(1.0, k))

    def _confidence(self, edge_val: float) -> str:
        if edge_val >= self._thresholds['high']:
            return "high"
        elif edge_val >= self._thresholds['medium']:
            return "medium"
        elif edge_val >= self._thresholds['low']:
            return "low"
        return "none"

    def evaluate_moneyline(self, game_id, home, away, h_odds, a_odds, h_prob) -> List[NFLValueBet]:
        bets = []
        now = datetime.now().isoformat()
        for team, odds, prob in [(home, h_odds, h_prob), (away, a_odds, 1 - h_prob)]:
            if not (self.min_odds <= odds <= self.max_odds):
                continue
            e = self.edge(prob, odds)
            if e >= self.value_threshold:
                k = self.kelly(prob, odds)
                bets.append(NFLValueBet(
                    game_id=game_id, market="moneyline", selection=team,
                    odds=odds, model_prob=prob, value=e, kelly=k,
                    bet_size=self.bankroll * k * self.kelly_fraction,
                    confidence=self._confidence(e), odds_timestamp=now))
        return bets

    def evaluate_spread(self, game_id, home, away, spread, h_odds, a_odds, h_cover) -> List[NFLValueBet]:
        bets = []
        now = datetime.now().isoformat()
        for team_label, odds, prob in [
            (f"{home} {spread:+.1f}", h_odds, h_cover),
            (f"{away} {-spread:+.1f}", a_odds, 1 - h_cover),
        ]:
            if not odds or not (self.min_odds <= odds <= self.max_odds):
                continue
            e = self.edge(prob, odds)
            if e >= self.value_threshold:
                k = self.kelly(prob, odds)
                bets.append(NFLValueBet(
                    game_id=game_id, market="spread", selection=team_label,
                    odds=odds, model_prob=prob, value=e, kelly=k,
                    bet_size=self.bankroll * k * self.kelly_fraction,
                    confidence=self._confidence(e), odds_timestamp=now))
        return bets

    def evaluate_totals(self, game_id: str, line: float,
                        over_odds: float, under_odds: float,
                        over_prob: float) -> List[NFLValueBet]:
        """NEW: Full totals evaluation."""
        bets = []
        now = datetime.now().isoformat()
        under_prob = 1.0 - over_prob

        for selection, odds, prob in [
            (f"Over {line}", over_odds, over_prob),
            (f"Under {line}", under_odds, under_prob),
        ]:
            if not odds or not (self.min_odds <= odds <= self.max_odds):
                continue
            e = self.edge(prob, odds)
            if e >= self.value_threshold:
                k = self.kelly(prob, odds)
                bets.append(NFLValueBet(
                    game_id=game_id, market="totals", selection=selection,
                    odds=odds, model_prob=prob, value=e, kelly=k,
                    bet_size=self.bankroll * k * self.kelly_fraction,
                    confidence=self._confidence(e), odds_timestamp=now))
        return bets

    def analyze_game(self, game_id: str, home: str, away: str,
                     odds_data: Dict, predictions: Dict) -> List[NFLValueBet]:
        """Full game analysis across all markets."""
        all_bets = []

        if "home_odds" in odds_data and "away_odds" in odds_data:
            all_bets.extend(self.evaluate_moneyline(
                game_id, home, away,
                odds_data["home_odds"], odds_data["away_odds"],
                predictions.get("home_win_prob", 0.5)))

        if "home_spread_odds" in odds_data:
            all_bets.extend(self.evaluate_spread(
                game_id, home, away,
                odds_data.get("spread", 0),
                odds_data.get("home_spread_odds"),
                odds_data.get("away_spread_odds"),
                predictions.get("home_cover_prob", 0.5)))

        if "over_odds" in odds_data:
            all_bets.extend(self.evaluate_totals(
                game_id,
                odds_data.get("total_line", 45),
                odds_data.get("over_odds"),
                odds_data.get("under_odds"),
                predictions.get("over_prob", 0.5)))

        return all_bets

    def to_dataframe(self, bets: List[NFLValueBet]) -> pd.DataFrame:
        if not bets:
            return pd.DataFrame()
        data = [{
            "game_id": b.game_id, "market": b.market, "selection": b.selection,
            "odds": b.odds, "model_prob": round(b.model_prob, 3),
            "value%": round(b.value * 100, 1), "kelly": round(b.kelly, 3),
            "bet_size": round(b.bet_size, 2), "conf": b.confidence,
        } for b in bets]
        df = pd.DataFrame(data)
        return df.sort_values("value%", ascending=False) if not df.empty else df

    @staticmethod
    def calculate_clv(opening_odds: float, closing_odds: float) -> float:
        if opening_odds <= 1.0 or closing_odds <= 1.0:
            return 0.0
        closing_imp = 1.0 / closing_odds
        opening_imp = 1.0 / opening_odds
        return (closing_imp - opening_imp) / opening_imp

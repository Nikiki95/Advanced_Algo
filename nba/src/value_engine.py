"""
NBA Value Bet Engine v2
- Uses Elo spread cover probability
- Uses pace-adjusted totals probability
- Injury confidence reduction
- CLV tracking
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
class ValueBet:
    game_id: str
    market: str         # moneyline, spread, totals
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


class NBAValueEngine:
    """
    NBA Value Engine v2 with full market support.
    """

    def __init__(self,
                 value_threshold: float = 0.05,
                 kelly_fraction: float = 0.25,
                 min_odds: float = 1.30,
                 max_odds: float = 10.0,
                 bankroll: float = 1000.0,
                 historical_performance: Optional[Dict] = None):
        self.value_threshold = value_threshold
        self.kelly_fraction = kelly_fraction
        self.min_odds = min_odds
        self.max_odds = max_odds
        self.bankroll = bankroll

        # Bayesian confidence calibration
        self._thresholds = {'high': 0.10, 'medium': 0.05, 'low': 0.03}
        if historical_performance:
            self._calibrate(historical_performance)

    def _calibrate(self, perf: Dict):
        total = perf.get('total_bets', 0)
        if total < 20:
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

    def calculate_edge(self, model_prob: float, market_odds: float) -> float:
        return model_prob - self.implied_prob(market_odds)

    def kelly_criterion(self, prob: float, odds: float) -> float:
        if odds <= 1.0 or prob <= 0:
            return 0.0
        b = odds - 1.0
        kelly = (b * prob - (1 - prob)) / b
        return max(0.0, min(1.0, kelly))

    def _bet_size(self, kelly: float) -> float:
        return self.bankroll * kelly * self.kelly_fraction

    def _confidence(self, edge: float) -> str:
        if edge >= self._thresholds['high']:
            return "high"
        elif edge >= self._thresholds['medium']:
            return "medium"
        elif edge >= self._thresholds['low']:
            return "low"
        return "none"

    def evaluate_moneyline(self, game_id: str, home_team: str, away_team: str,
                           home_odds: float, away_odds: float,
                           home_win_prob: float) -> List[ValueBet]:
        bets = []
        now = datetime.now().isoformat()
        for team, odds, prob in [
            (home_team, home_odds, home_win_prob),
            (away_team, away_odds, 1.0 - home_win_prob),
        ]:
            if not (self.min_odds <= odds <= self.max_odds):
                continue
            edge = self.calculate_edge(prob, odds)
            if edge >= self.value_threshold:
                k = self.kelly_criterion(prob, odds)
                bets.append(ValueBet(
                    game_id=game_id, market="moneyline", selection=team,
                    odds=odds, model_prob=prob, value=edge,
                    kelly=k, bet_size=self._bet_size(k),
                    confidence=self._confidence(edge),
                    odds_timestamp=now))
        return bets

    def evaluate_spread(self, game_id: str, home_team: str, away_team: str,
                        home_spread: float, home_spread_odds: float,
                        away_spread_odds: float,
                        home_cover_prob: float) -> List[ValueBet]:
        bets = []
        now = datetime.now().isoformat()
        spread_threshold = self.value_threshold * 0.6

        for team, odds, prob, spread_val in [
            (f"{home_team} {home_spread:+.1f}", home_spread_odds, home_cover_prob, home_spread),
            (f"{away_team} {-home_spread:+.1f}", away_spread_odds, 1 - home_cover_prob, -home_spread),
        ]:
            if not odds or not (self.min_odds <= odds <= self.max_odds):
                continue
            edge = self.calculate_edge(prob, odds)
            if edge >= spread_threshold:
                k = self.kelly_criterion(prob, odds)
                bets.append(ValueBet(
                    game_id=game_id, market="spread", selection=team,
                    odds=odds, model_prob=prob, value=edge,
                    kelly=k, bet_size=self._bet_size(k),
                    confidence=self._confidence(edge),
                    odds_timestamp=now))
        return bets

    def evaluate_totals(self, game_id: str, over_line: float,
                        over_odds: float, under_odds: float,
                        over_prob: float) -> List[ValueBet]:
        bets = []
        now = datetime.now().isoformat()
        under_prob = 1.0 - over_prob

        for selection, odds, prob in [
            (f"Over {over_line}", over_odds, over_prob),
            (f"Under {over_line}", under_odds, under_prob),
        ]:
            if not odds or not (self.min_odds <= odds <= self.max_odds):
                continue
            edge = self.calculate_edge(prob, odds)
            if edge >= self.value_threshold:
                k = self.kelly_criterion(prob, odds)
                bets.append(ValueBet(
                    game_id=game_id, market="totals", selection=selection,
                    odds=odds, model_prob=prob, value=edge,
                    kelly=k, bet_size=self._bet_size(k),
                    confidence=self._confidence(edge),
                    odds_timestamp=now))
        return bets

    def analyze_game(self, game_id: str, home_team: str, away_team: str,
                     odds_data: Dict, model_predictions: Dict,
                     home_impact: Dict = None, away_impact: Dict = None) -> List[ValueBet]:
        """Full game analysis across all markets."""
        all_bets = []
        home_impact = home_impact or {}
        away_impact = away_impact or {}
        injury_reduction = max(
            home_impact.get('confidence_reduction', 0),
            away_impact.get('confidence_reduction', 0))

        # Moneyline
        if "home_odds" in odds_data and "away_odds" in odds_data:
            all_bets.extend(self.evaluate_moneyline(
                game_id, home_team, away_team,
                odds_data["home_odds"], odds_data["away_odds"],
                model_predictions.get("home_win_prob", 0.5)))

        # Spread
        if "home_spread_odds" in odds_data:
            all_bets.extend(self.evaluate_spread(
                game_id, home_team, away_team,
                odds_data.get("home_spread", 0),
                odds_data.get("home_spread_odds"),
                odds_data.get("away_spread_odds"),
                model_predictions.get("home_cover_prob", 0.5)))

        # Totals (NEW: actually uses model predictions now)
        if "over_odds" in odds_data:
            all_bets.extend(self.evaluate_totals(
                game_id,
                odds_data.get("over_line", 220),
                odds_data.get("over_odds"),
                odds_data.get("under_odds"),
                model_predictions.get("over_prob", 0.5)))

        # Injury confidence downgrade
        if injury_reduction > 0:
            for bet in all_bets:
                if injury_reduction >= 0.15:
                    if bet.confidence == 'high':
                        bet.confidence = 'medium'
                    elif bet.confidence == 'medium':
                        bet.confidence = 'low'
                elif injury_reduction >= 0.10:
                    if bet.confidence == 'high' and bet.value < 0.08:
                        bet.confidence = 'medium'

        return all_bets

    def get_best_bets(self, all_bets: List[ValueBet],
                      min_confidence: str = "medium",
                      max_bets: int = 10) -> List[ValueBet]:
        order = {"high": 3, "medium": 2, "low": 1, "none": 0}
        min_level = order.get(min_confidence, 2)
        filtered = [b for b in all_bets if order.get(b.confidence, 0) >= min_level]
        return sorted(filtered, key=lambda x: x.value, reverse=True)[:max_bets]

    # ── CLV ──────────────────────────────────────

    @staticmethod
    def calculate_clv(opening_odds: float, closing_odds: float) -> float:
        if opening_odds <= 1.0 or closing_odds <= 1.0:
            return 0.0
        closing_imp = 1.0 / closing_odds
        opening_imp = 1.0 / opening_odds
        return (closing_imp - opening_imp) / opening_imp

    # ── REPORTING ────────────────────────────────

    def to_dataframe(self, bets: List[ValueBet]) -> pd.DataFrame:
        if not bets:
            return pd.DataFrame()
        data = [{
            "game_id": b.game_id, "market": b.market, "selection": b.selection,
            "odds": b.odds, "model_prob": round(b.model_prob, 3),
            "value": round(b.value * 100, 1), "kelly": round(b.kelly, 3),
            "bet_size": round(b.bet_size, 2), "confidence": b.confidence,
            "ev": round(b.model_prob * b.odds - 1, 3),
        } for b in bets]
        df = pd.DataFrame(data)
        return df.sort_values("value", ascending=False).reset_index(drop=True) if not df.empty else df

    def summary(self, bets: List[ValueBet]) -> str:
        if not bets:
            return "Keine Value-Bets gefunden."
        lines = [
            f"==== NBA Value Bets ====",
            f"Gefunden: {len(bets)} | Bankroll: ${self.bankroll:,.2f}",
            f"\nTop 5:",
        ]
        for i, b in enumerate(bets[:5], 1):
            lines.append(
                f"{i}. {b.selection} ({b.market}) @ {b.odds:.2f} | "
                f"Edge: {b.value*100:+.1f}% | Kelly: {b.kelly:.1%} | "
                f"${b.bet_size:.2f}")
        return "\n".join(lines)

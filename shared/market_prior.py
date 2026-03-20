"""
Market Prior Integration v1

Bayesian combination of model predictions with market odds.

Instead of treating your model as ground truth and the market as noise,
this module treats the market as a highly informative prior and your
model as an update on that prior.

posterior = alpha * model + (1 - alpha) * market

Alpha is optimized from CLV data — higher alpha when your model has
proven it beats the market (positive CLV), lower when it hasn't.

Works for: Football, NBA, NFL
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PriorAdjustedPrediction:
    """Prediction after market prior integration."""
    home_team: str
    away_team: str

    # Original model probabilities
    raw_model_home: float
    raw_model_draw: float   # 0 for NBA/NFL
    raw_model_away: float

    # Market-implied probabilities (vig-removed)
    market_home: float
    market_draw: float
    market_away: float

    # Posterior (combined) probabilities
    posterior_home: float
    posterior_draw: float
    posterior_away: float

    # Alpha used (model weight)
    alpha: float

    # Value vs market (using posterior)
    value_home: float = 0.0
    value_draw: float = 0.0
    value_away: float = 0.0


class MarketPrior:
    """
    Combines model predictions with market odds using Bayesian averaging.

    Key insight: Bookmaker odds aggregate millions of euros of information.
    Pure model predictions ignore this. By combining both, we get:
    - Lower variance (less wild predictions)
    - Better calibration (predictions closer to true probabilities)
    - Edge detection only where model genuinely disagrees with market

    Alpha calibration:
    - alpha = 1.0 → pure model (no market influence)
    - alpha = 0.5 → equal weight
    - alpha = 0.3 → mostly market (conservative)

    Optimal alpha is learned from CLV data.
    """

    DEFAULT_ALPHA = 0.40  # Conservative default: model gets 40% weight

    # Alpha bounds
    ALPHA_MIN = 0.15      # Never trust market completely
    ALPHA_MAX = 0.80      # Never ignore market completely

    def __init__(self, alpha: float = None,
                 clv_data: Optional[Dict] = None,
                 sport: str = "football"):
        """
        Args:
            alpha: Model weight (None = auto from CLV data)
            clv_data: CLV analysis dict from feedback loop
            sport: Sport identifier (affects defaults)
        """
        self.sport = sport

        # Sport-specific defaults
        self._sport_defaults = {
            'football': 0.40,  # Football markets are very efficient
            'nba': 0.45,       # NBA has more edges (injuries, B2B)
            'nfl': 0.35,       # NFL markets extremely efficient
        }

        if alpha is not None:
            self.alpha = np.clip(alpha, self.ALPHA_MIN, self.ALPHA_MAX)
        elif clv_data is not None:
            self.alpha = self._calibrate_alpha(clv_data)
        else:
            self.alpha = self._sport_defaults.get(sport, self.DEFAULT_ALPHA)

        logger.info(f"MarketPrior initialized: alpha={self.alpha:.3f} ({sport})")

    def _calibrate_alpha(self, clv_data: Dict) -> float:
        """
        Calibrate alpha from CLV data.

        If CLV is strongly positive → increase alpha (trust model more)
        If CLV is negative → decrease alpha (trust market more)
        """
        if not clv_data.get('available', False):
            return self._sport_defaults.get(self.sport, self.DEFAULT_ALPHA)

        avg_clv = clv_data.get('avg_clv_percent', 0) / 100  # Convert from percent
        positive_rate = clv_data.get('positive_clv_rate', 50) / 100
        n_tracked = clv_data.get('total_tracked', 0)

        # Base alpha from sport
        base = self._sport_defaults.get(self.sport, self.DEFAULT_ALPHA)

        # Adjustment based on CLV
        if n_tracked < 20:
            # Not enough data — use default
            logger.info(f"  Only {n_tracked} CLV datapoints, using default alpha")
            return base

        # CLV-based adjustment
        # Positive CLV → model is beating the market → increase alpha
        # avg_clv of +3% ≈ +0.15 to alpha
        clv_adjustment = avg_clv * 5.0  # Scale factor

        # Positive rate adjustment
        # 60% positive CLV rate → +0.05 to alpha
        rate_adjustment = (positive_rate - 0.5) * 0.5

        adjusted = base + clv_adjustment + rate_adjustment
        final = np.clip(adjusted, self.ALPHA_MIN, self.ALPHA_MAX)

        logger.info(f"  CLV calibration: base={base:.3f}, CLV_adj={clv_adjustment:+.3f}, "
                    f"rate_adj={rate_adjustment:+.3f} → alpha={final:.3f}")
        return float(final)

    # ────────────────────────────────────────────
    # CORE: COMBINE MODEL + MARKET
    # ────────────────────────────────────────────

    def combine(self,
                model_probs: Dict[str, float],
                market_odds: Dict[str, float],
                alpha_override: float = None) -> Dict[str, float]:
        """
        Combine model probabilities with market-implied probabilities.

        Args:
            model_probs: {'1': 0.55, 'X': 0.25, '2': 0.20}
            market_odds: {'1': 1.80, 'X': 3.50, '2': 4.00}
                        OR implied probs: {'1': 0.56, 'X': 0.29, '2': 0.25}
            alpha_override: Override the calibrated alpha

        Returns:
            Posterior probabilities: {'1': float, 'X': float, '2': float}
        """
        alpha = alpha_override if alpha_override is not None else self.alpha

        # Convert odds to probabilities if needed
        market_probs = self._odds_to_fair_probs(market_odds)

        # Bayesian combination
        posterior = {}
        for outcome in model_probs:
            mp = model_probs.get(outcome, 0)
            mk = market_probs.get(outcome, mp)  # Fallback to model if no market
            posterior[outcome] = alpha * mp + (1 - alpha) * mk

        # Normalize to sum to 1
        total = sum(posterior.values())
        if total > 0:
            posterior = {k: v / total for k, v in posterior.items()}

        return posterior

    def adjust_football_prediction(self,
                                    prediction,
                                    odds_data,
                                    alpha_override: float = None) -> PriorAdjustedPrediction:
        """
        Full adjustment for a football MatchPrediction + OddsData.
        Returns PriorAdjustedPrediction with original, market, and posterior probs.
        """
        model_probs = {
            '1': prediction.prob_home_win,
            'X': prediction.prob_draw,
            '2': prediction.prob_away_win,
        }

        # Get best market odds
        market_odds = {}
        if hasattr(odds_data, 'odds_1') and odds_data.odds_1:
            market_odds['1'] = max(odds_data.odds_1.values())
        if hasattr(odds_data, 'odds_x') and odds_data.odds_x:
            market_odds['X'] = max(odds_data.odds_x.values())
        if hasattr(odds_data, 'odds_2') and odds_data.odds_2:
            market_odds['2'] = max(odds_data.odds_2.values())

        if not market_odds:
            # No market data — return raw model
            return PriorAdjustedPrediction(
                home_team=prediction.home_team,
                away_team=prediction.away_team,
                raw_model_home=model_probs['1'],
                raw_model_draw=model_probs['X'],
                raw_model_away=model_probs['2'],
                market_home=0, market_draw=0, market_away=0,
                posterior_home=model_probs['1'],
                posterior_draw=model_probs['X'],
                posterior_away=model_probs['2'],
                alpha=1.0)

        market_fair = self._odds_to_fair_probs(market_odds)
        posterior = self.combine(model_probs, market_odds, alpha_override)

        # Value = posterior - market_implied (using fair probs)
        value_home = posterior.get('1', 0) - market_fair.get('1', 0)
        value_draw = posterior.get('X', 0) - market_fair.get('X', 0)
        value_away = posterior.get('2', 0) - market_fair.get('2', 0)

        return PriorAdjustedPrediction(
            home_team=prediction.home_team,
            away_team=prediction.away_team,
            raw_model_home=model_probs['1'],
            raw_model_draw=model_probs['X'],
            raw_model_away=model_probs['2'],
            market_home=market_fair.get('1', 0),
            market_draw=market_fair.get('X', 0),
            market_away=market_fair.get('2', 0),
            posterior_home=posterior.get('1', 0),
            posterior_draw=posterior.get('X', 0),
            posterior_away=posterior.get('2', 0),
            alpha=alpha_override or self.alpha,
            value_home=value_home,
            value_draw=value_draw,
            value_away=value_away)

    def adjust_binary_prediction(self,
                                  model_home_prob: float,
                                  home_odds: float,
                                  away_odds: float,
                                  alpha_override: float = None) -> Dict:
        """
        Adjust for binary outcome sports (NBA, NFL).

        Returns:
            {'home_prob': float, 'away_prob': float, 'alpha': float,
             'raw_home': float, 'market_home': float}
        """
        model_probs = {'home': model_home_prob, 'away': 1 - model_home_prob}
        market_odds = {'home': home_odds, 'away': away_odds}
        market_fair = self._odds_to_fair_probs(market_odds)

        posterior = self.combine(model_probs, market_odds, alpha_override)

        return {
            'home_prob': posterior.get('home', model_home_prob),
            'away_prob': posterior.get('away', 1 - model_home_prob),
            'alpha': alpha_override or self.alpha,
            'raw_home': model_home_prob,
            'market_home': market_fair.get('home', 0),
        }

    # ────────────────────────────────────────────
    # ODDS → FAIR PROBABILITIES
    # ────────────────────────────────────────────

    def _odds_to_fair_probs(self, odds_or_probs: Dict[str, float]) -> Dict[str, float]:
        """
        Convert decimal odds to fair (vig-removed) probabilities.
        If values already look like probabilities (all < 1), pass through.
        """
        values = list(odds_or_probs.values())

        # Detect if already probabilities
        if all(0 < v < 1 for v in values):
            # Already probabilities, just normalize
            total = sum(values)
            return {k: v / total for k, v in odds_or_probs.items()}

        # Convert from decimal odds
        if any(v <= 1.0 for v in values):
            # Invalid odds
            return odds_or_probs

        raw_probs = {k: 1.0 / v for k, v in odds_or_probs.items()}
        overround = sum(raw_probs.values())

        # Remove vig proportionally (most common method)
        if overround > 0:
            fair = {k: v / overround for k, v in raw_probs.items()}
        else:
            fair = raw_probs

        return fair

    # ────────────────────────────────────────────
    # ALPHA GRID SEARCH (for backtesting)
    # ────────────────────────────────────────────

    @staticmethod
    def grid_search_alpha(model_predictions: List[Dict],
                          alpha_range: Tuple = (0.15, 0.80),
                          steps: int = 14) -> Dict:
        """
        Find optimal alpha via grid search on historical predictions.

        Args:
            model_predictions: List of dicts with:
                {'model_prob': float, 'market_odds': float,
                 'actual_won': bool, 'bet_type': str}
            alpha_range: (min_alpha, max_alpha)
            steps: Number of alphas to test

        Returns:
            {'optimal_alpha': float, 'best_roi': float, 'all_results': [...]}
        """
        alphas = np.linspace(alpha_range[0], alpha_range[1], steps)
        results = []

        for alpha in alphas:
            total_profit = 0
            total_staked = 0
            bets_taken = 0

            for pred in model_predictions:
                mp = pred['model_prob']
                odds = pred['market_odds']
                won = pred['actual_won']

                market_prob = 1.0 / odds if odds > 1 else 0
                posterior = alpha * mp + (1 - alpha) * market_prob
                value = posterior - market_prob

                if value >= 0.05:  # 5% threshold
                    stake = 10.0
                    total_staked += stake
                    bets_taken += 1
                    total_profit += stake * (odds - 1) if won else -stake

            roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
            results.append({
                'alpha': round(float(alpha), 3),
                'bets': bets_taken,
                'roi': round(roi, 2),
                'profit': round(total_profit, 2),
            })

        best = max(results, key=lambda x: x['roi'])
        logger.info(f"Grid search: optimal alpha={best['alpha']}, ROI={best['roi']}%")

        return {
            'optimal_alpha': best['alpha'],
            'best_roi': best['roi'],
            'all_results': results,
        }

    # ────────────────────────────────────────────
    # PERSISTENCE
    # ────────────────────────────────────────────

    def save_alpha(self, path: Path = None):
        """Save calibrated alpha for next session."""
        path = path or Path("data/market_prior_alpha.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump({
                'alpha': self.alpha,
                'sport': self.sport,
                'timestamp': str(datetime.now()) if 'datetime' in dir() else 'unknown',
            }, f, indent=2)

    @classmethod
    def load_alpha(cls, path: Path = None, sport: str = "football") -> 'MarketPrior':
        """Load calibrated alpha from previous session."""
        path = path or Path("data/market_prior_alpha.json")
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return cls(alpha=data.get('alpha'), sport=sport)
        return cls(sport=sport)


# Convenience: import datetime if available
try:
    from datetime import datetime
except ImportError:
    pass

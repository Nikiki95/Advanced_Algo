"""
Walk-Forward Backtesting Framework v1

Systematic out-of-sample testing for all models.

Walk-forward approach:
1. Train on data up to day T
2. Predict matches on day T+1
3. Evaluate predictions against actual results
4. Slide window forward and repeat

Works for: Football (Dixon-Coles), NBA (Elo), NFL (Power Rankings)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BetPrediction:
    """Single prediction for backtesting."""
    date: str
    home_team: str
    away_team: str
    bet_type: str          # '1', 'X', '2', 'Over_2.5', etc.
    model_prob: float
    market_prob: float     # From odds
    odds: float
    value: float           # model_prob - market_prob

    # Actual outcome (filled after evaluation)
    actual_result: Optional[str] = None  # 'win', 'loss'
    profit_loss: Optional[float] = None


@dataclass
class BacktestResult:
    """Results of a complete backtest run."""
    sport: str
    model_name: str
    start_date: str
    end_date: str
    total_matches: int
    total_predictions: int    # Predictions that met value threshold

    # Core metrics
    win_rate: float
    roi_percent: float
    total_profit: float
    total_staked: float

    # CLV proxy (model vs closing line)
    avg_value: float          # Average value of taken bets
    avg_positive_ev: float    # Average EV of taken bets

    # By confidence
    high_conf_bets: int = 0
    high_conf_wr: float = 0.0
    medium_conf_bets: int = 0
    medium_conf_wr: float = 0.0

    # By market type
    market_breakdown: Dict = field(default_factory=dict)

    # Calibration (predicted vs actual probability)
    calibration_buckets: Dict = field(default_factory=dict)

    # Sharpe-like metric
    daily_returns: List[float] = field(default_factory=list)
    sharpe_ratio: float = 0.0

    # Model info
    parameters: Dict = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"{'='*60}",
            f"BACKTEST: {self.sport} / {self.model_name}",
            f"Period: {self.start_date} → {self.end_date}",
            f"{'='*60}",
            f"Matches: {self.total_matches} | Bets: {self.total_predictions}",
            f"Win-Rate: {self.win_rate:.1f}% | ROI: {self.roi_percent:+.2f}%",
            f"Profit: {self.total_profit:+.2f} | Staked: {self.total_staked:.2f}",
            f"Avg Value: {self.avg_value*100:.2f}% | Avg EV: {self.avg_positive_ev*100:.2f}%",
            f"Sharpe: {self.sharpe_ratio:.2f}",
        ]
        if self.high_conf_bets > 0:
            lines.append(f"High Conf: {self.high_conf_bets} bets, {self.high_conf_wr:.1f}% WR")
        if self.medium_conf_bets > 0:
            lines.append(f"Med Conf: {self.medium_conf_bets} bets, {self.medium_conf_wr:.1f}% WR")
        if self.market_breakdown:
            lines.append("Markets:")
            for m, stats in self.market_breakdown.items():
                lines.append(f"  {m}: {stats['bets']}x, WR {stats['wr']:.1f}%, ROI {stats['roi']:+.1f}%")
        if self.calibration_buckets:
            lines.append("Calibration (predicted → actual):")
            for bucket, cal in sorted(self.calibration_buckets.items()):
                lines.append(f"  {bucket}: predicted {cal['avg_pred']:.1%} → actual {cal['actual']:.1%} ({cal['n']} bets)")
        lines.append(f"{'='*60}")
        return "\n".join(lines)


class WalkForwardBacktester:
    """
    Walk-forward backtesting engine.

    Usage:
        bt = WalkForwardBacktester(
            train_fn=my_train_function,
            predict_fn=my_predict_function,
            evaluate_fn=my_evaluate_function,
        )
        result = bt.run(data, train_window_days=365, step_days=7)
    """

    def __init__(self,
                 train_fn: Callable,
                 predict_fn: Callable,
                 evaluate_fn: Callable,
                 sport: str = "football",
                 model_name: str = "default",
                 value_threshold: float = 0.05,
                 kelly_fraction: float = 0.25,
                 bankroll: float = 1000.0):
        """
        Args:
            train_fn: (train_data: DataFrame) -> model
                Trains the model on historical data

            predict_fn: (model, test_data: DataFrame) -> List[BetPrediction]
                Generates predictions for upcoming matches

            evaluate_fn: (predictions: List[BetPrediction], results: DataFrame) -> List[BetPrediction]
                Evaluates predictions against actual results, fills actual_result and profit_loss

            sport: Sport identifier
            model_name: Model identifier for logging
            value_threshold: Minimum value to place bet
            kelly_fraction: Kelly fraction for bet sizing
        """
        self.train_fn = train_fn
        self.predict_fn = predict_fn
        self.evaluate_fn = evaluate_fn
        self.sport = sport
        self.model_name = model_name
        self.value_threshold = value_threshold
        self.kelly_fraction = kelly_fraction
        self.bankroll = bankroll

    def run(self, data: pd.DataFrame,
            train_window_days: int = 365,
            step_days: int = 7,
            min_train_matches: int = 100) -> BacktestResult:
        """
        Run walk-forward backtest.

        Args:
            data: Full dataset with Date column
            train_window_days: Rolling training window size
            step_days: Days to advance per step
            min_train_matches: Minimum matches needed to train
        """
        data = data.sort_values('Date').reset_index(drop=True)
        dates = pd.to_datetime(data['Date'])
        min_date = dates.min()
        max_date = dates.max()

        # Start after initial training window
        start = min_date + timedelta(days=train_window_days)
        current = start

        all_predictions = []
        step_count = 0

        logger.info(f"Backtest: {self.sport}/{self.model_name}")
        logger.info(f"Data: {min_date.date()} → {max_date.date()} ({len(data)} matches)")
        logger.info(f"Window: {train_window_days}d, Step: {step_days}d")

        while current < max_date:
            step_end = current + timedelta(days=step_days)

            # Training data: everything before current date
            if train_window_days > 0:
                train_start = current - timedelta(days=train_window_days)
                train_data = data[(dates >= train_start) & (dates < current)]
            else:
                train_data = data[dates < current]

            # Test data: matches in the step window
            test_data = data[(dates >= current) & (dates < step_end)]

            if len(train_data) < min_train_matches or len(test_data) == 0:
                current = step_end
                continue

            # Train
            try:
                model = self.train_fn(train_data)
            except Exception as e:
                logger.warning(f"Training failed at {current.date()}: {e}")
                current = step_end
                continue

            # Predict
            try:
                predictions = self.predict_fn(model, test_data)
            except Exception as e:
                logger.warning(f"Prediction failed at {current.date()}: {e}")
                current = step_end
                continue

            # Filter by value threshold
            value_bets = [p for p in predictions if p.value >= self.value_threshold]

            # Evaluate against actual results
            if value_bets:
                try:
                    evaluated = self.evaluate_fn(value_bets, test_data)
                    all_predictions.extend(evaluated)
                except Exception as e:
                    logger.warning(f"Evaluation failed at {current.date()}: {e}")

            step_count += 1
            if step_count % 10 == 0:
                logger.info(f"  Step {step_count}: {current.date()} | "
                          f"{len(all_predictions)} bets so far")

            current = step_end

        # Compile results
        logger.info(f"Backtest complete: {step_count} steps, {len(all_predictions)} bets")
        return self._compile_results(all_predictions, data, start, max_date)

    def _compile_results(self, predictions: List[BetPrediction],
                         data: pd.DataFrame,
                         start_date, end_date) -> BacktestResult:
        """Compile all predictions into a BacktestResult."""
        if not predictions:
            return BacktestResult(
                sport=self.sport, model_name=self.model_name,
                start_date=str(start_date.date()), end_date=str(end_date.date()),
                total_matches=len(data), total_predictions=0,
                win_rate=0, roi_percent=0, total_profit=0, total_staked=0,
                avg_value=0, avg_positive_ev=0)

        settled = [p for p in predictions if p.actual_result is not None]
        if not settled:
            return BacktestResult(
                sport=self.sport, model_name=self.model_name,
                start_date=str(start_date.date()), end_date=str(end_date.date()),
                total_matches=len(data), total_predictions=len(predictions),
                win_rate=0, roi_percent=0, total_profit=0, total_staked=0,
                avg_value=np.mean([p.value for p in predictions]),
                avg_positive_ev=np.mean([p.model_prob * p.odds - 1 for p in predictions]))

        wins = sum(1 for p in settled if p.actual_result == 'win')
        losses = sum(1 for p in settled if p.actual_result == 'loss')
        wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0

        # P&L
        total_profit = sum(p.profit_loss for p in settled if p.profit_loss is not None)
        stake_per_bet = self.bankroll * self.kelly_fraction * 0.05  # ~5% avg
        total_staked = len(settled) * stake_per_bet
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0

        # Daily returns for Sharpe
        daily_pnl = {}
        for p in settled:
            d = p.date[:10]
            daily_pnl.setdefault(d, 0)
            if p.profit_loss:
                daily_pnl[d] += p.profit_loss

        daily_returns = list(daily_pnl.values())
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe = 0

        # Calibration
        calibration = self._calibration_analysis(settled)

        # Market breakdown
        market_stats = {}
        for market in set(p.bet_type.split('_')[0] for p in settled):
            mb = [p for p in settled if p.bet_type.startswith(market)]
            mw = sum(1 for p in mb if p.actual_result == 'win')
            ml = sum(1 for p in mb if p.actual_result == 'loss')
            mp = sum(p.profit_loss for p in mb if p.profit_loss is not None)
            ms = len(mb) * stake_per_bet
            market_stats[market] = {
                'bets': len(mb),
                'wr': mw / (mw + ml) * 100 if (mw + ml) > 0 else 0,
                'roi': mp / ms * 100 if ms > 0 else 0,
            }

        return BacktestResult(
            sport=self.sport, model_name=self.model_name,
            start_date=str(start_date.date()), end_date=str(end_date.date()),
            total_matches=len(data), total_predictions=len(settled),
            win_rate=wr, roi_percent=roi,
            total_profit=total_profit, total_staked=total_staked,
            avg_value=np.mean([p.value for p in settled]),
            avg_positive_ev=np.mean([p.model_prob * p.odds - 1 for p in settled]),
            market_breakdown=market_stats,
            calibration_buckets=calibration,
            daily_returns=daily_returns,
            sharpe_ratio=sharpe)

    def _calibration_analysis(self, predictions: List[BetPrediction]) -> Dict:
        """
        Calibration: Do predicted probabilities match actual win rates?
        Buckets: 0.3-0.4, 0.4-0.5, 0.5-0.6, 0.6-0.7, 0.7+
        """
        buckets = {}
        ranges = [(0.3, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 1.0)]

        for low, high in ranges:
            bucket_preds = [p for p in predictions if low <= p.model_prob < high]
            if len(bucket_preds) >= 5:
                wins = sum(1 for p in bucket_preds if p.actual_result == 'win')
                actual_wr = wins / len(bucket_preds)
                avg_pred = np.mean([p.model_prob for p in bucket_preds])
                buckets[f"{low:.0%}-{high:.0%}"] = {
                    'n': len(bucket_preds),
                    'avg_pred': avg_pred,
                    'actual': actual_wr,
                    'gap': actual_wr - avg_pred,
                }

        return buckets


# ── CONVENIENCE FACTORIES ────────────────────────

def create_football_backtester(value_threshold: float = 0.05,
                                training_mode: str = 'xg') -> WalkForwardBacktester:
    """
    Factory for football backtesting.

    Example:
        bt = create_football_backtester(training_mode='xg')
        data = xg_fetcher.fetch_training_data('D1', seasons=3)
        result = bt.run(data, train_window_days=365, step_days=7)
        print(result.summary())
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "football" / "src"))

    def train_fn(train_data):
        from model.dixon_coles import DixonColesModel
        model = DixonColesModel(training_mode=training_mode)
        model.fit(train_data)
        return model

    def predict_fn(model, test_data):
        predictions = []
        for _, row in test_data.iterrows():
            pred = model.predict(row['HomeTeam'], row['AwayTeam'])
            if pred is None:
                continue
            # Check all three outcomes
            for bt, prob in [('1', pred.prob_home_win),
                             ('X', pred.prob_draw),
                             ('2', pred.prob_away_win)]:
                # Simulate market odds from football-data columns
                odds_col = {'1': 'B365H', 'X': 'B365D', '2': 'B365A'}.get(bt)
                if odds_col and odds_col in row.index and pd.notna(row.get(odds_col)):
                    odds = float(row[odds_col])
                    if odds > 1.0:
                        market_prob = 1.0 / odds
                        value = prob - market_prob
                        predictions.append(BetPrediction(
                            date=str(row['Date']),
                            home_team=row['HomeTeam'], away_team=row['AwayTeam'],
                            bet_type=bt, model_prob=prob,
                            market_prob=market_prob, odds=odds, value=value))

            # Over/Under 2.5
            if pred.expected_home_goals and pred.expected_away_goals:
                from scipy.stats import poisson
                total_xg = pred.expected_home_goals + pred.expected_away_goals
                over_prob = 1 - poisson.cdf(2, total_xg)  # P(goals >= 3)

                for bt, prob, odds_col in [
                    ('Over', over_prob, 'B365>2.5'),
                    ('Under', 1 - over_prob, 'B365<2.5')
                ]:
                    if odds_col in row.index and pd.notna(row.get(odds_col)):
                        odds = float(row[odds_col])
                        if odds > 1.0:
                            market_prob = 1.0 / odds
                            value = prob - market_prob
                            predictions.append(BetPrediction(
                                date=str(row['Date']),
                                home_team=row['HomeTeam'], away_team=row['AwayTeam'],
                                bet_type=f'{bt}_2.5', model_prob=prob,
                                market_prob=market_prob, odds=odds, value=value))

        return predictions

    def evaluate_fn(predictions, results):
        for pred in predictions:
            # Find matching result
            for _, row in results.iterrows():
                if (str(row['HomeTeam']) == pred.home_team and
                    str(row['AwayTeam']) == pred.away_team):
                    h, a = int(row['FTHG']), int(row['FTAG'])
                    actual = 'H' if h > a else ('A' if a > h else 'D')
                    total = h + a

                    if pred.bet_type == '1':
                        won = actual == 'H'
                    elif pred.bet_type == '2':
                        won = actual == 'A'
                    elif pred.bet_type == 'X':
                        won = actual == 'D'
                    elif pred.bet_type == 'Over_2.5':
                        won = total > 2
                    elif pred.bet_type == 'Under_2.5':
                        won = total < 3
                    else:
                        continue

                    pred.actual_result = 'win' if won else 'loss'
                    stake = 10.0  # Fixed stake for backtesting
                    pred.profit_loss = stake * (pred.odds - 1) if won else -stake
                    break

        return [p for p in predictions if p.actual_result is not None]

    return WalkForwardBacktester(
        train_fn=train_fn, predict_fn=predict_fn, evaluate_fn=evaluate_fn,
        sport="football", model_name=f"Dixon-Coles ({training_mode})",
        value_threshold=value_threshold)


def save_backtest_result(result: BacktestResult, path: Path = None):
    """Save backtest results to JSON."""
    path = path or Path("data/backtests")
    path.mkdir(parents=True, exist_ok=True)
    filename = f"bt_{result.sport}_{result.model_name}_{result.start_date}.json"
    filepath = path / filename.replace(' ', '_').replace('/', '_')

    out = asdict(result)
    with open(filepath, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    logger.info(f"Saved: {filepath}")
    return filepath


def compare_backtests(*results: BacktestResult) -> str:
    """Compare multiple backtest results side by side."""
    lines = [f"{'Model':<30} {'Bets':>5} {'WR':>6} {'ROI':>8} {'Profit':>8} {'Sharpe':>7}"]
    lines.append("-" * 70)
    for r in results:
        lines.append(
            f"{r.model_name:<30} {r.total_predictions:>5} "
            f"{r.win_rate:>5.1f}% {r.roi_percent:>+7.2f}% "
            f"{r.total_profit:>+7.2f} {r.sharpe_ratio:>7.2f}")
    return "\n".join(lines)

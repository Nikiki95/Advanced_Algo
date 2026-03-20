"""
Value-Engine v2: Full market coverage with Over/Under, Double Chance,
Closing Line Value tracking, and Bayesian confidence scoring.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import numpy as np
from scipy.stats import poisson

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

try:
    from config import football_config as cfg
except ImportError:
    cfg = None

# Defaults when config not available
_MIN_VALUE = getattr(cfg, 'MIN_VALUE_THRESHOLD', 0.05) if cfg else 0.05
_KELLY_FRAC = getattr(cfg, 'KELLY_FRACTION', 0.25) if cfg else 0.25
_OU_THRESH = getattr(cfg, 'OU_VALUE_THRESHOLD', 0.04) if cfg else 0.04
_DC_THRESH = getattr(cfg, 'DC_VALUE_THRESHOLD', 0.03) if cfg else 0.03
_MAX_GOALS = getattr(cfg, 'OU_MAX_GOALS', 7) if cfg else 7
_OU_LINE = getattr(cfg, 'OU_DEFAULT_LINE', 2.5) if cfg else 2.5


@dataclass
class ValueBet:
    """Ein identifizierter Value-Bet"""
    home_team: str
    away_team: str
    league: str
    match_datetime: datetime
    bet_type: str       # '1','X','2','1X','X2','12','Over_2.5','Under_2.5'
    selection: str
    model_probability: float
    market_probability: float
    best_odds: float
    bookmaker: str
    value_percentage: float
    expected_value: float
    kelly_stake: float
    confidence: str     # 'high', 'medium', 'low'

    # CLV tracking
    odds_timestamp: Optional[str] = None
    closing_odds: Optional[float] = None
    clv: Optional[float] = None

    @property
    def roi(self) -> float:
        return self.expected_value * 100

    def __str__(self) -> str:
        return (f"ValueBet({self.home_team} vs {self.away_team}: "
                f"{self.bet_type} @ {self.best_odds:.2f}, "
                f"Value: {self.value_percentage:.1%})")


class ValueEngine:
    """
    Value Engine v2:
    - 1X2, Double Chance, Over/Under
    - Closing Line Value tracking
    - Bayesian confidence (calibrated from feedback loop)
    - Correlated bet detection
    """

    def __init__(self, historical_performance: Optional[Dict] = None):
        self.min_value = _MIN_VALUE
        self.kelly_fraction = _KELLY_FRAC
        self.ou_threshold = _OU_THRESH
        self.dc_threshold = _DC_THRESH
        self.max_goals = _MAX_GOALS

        self._base_thresholds = {'high': 0.10, 'medium': 0.05, 'low': 0.02}
        if historical_performance:
            self._calibrate_confidence(historical_performance)

    # ── PUBLIC ──────────────────────────────────

    def analyze_match(self, prediction, odds_data,
                      bankroll: float = 1000.0,
                      ou_odds: Optional[Dict] = None) -> List[ValueBet]:
        value_bets = []
        value_bets.extend(self._check_1x2(prediction, odds_data, bankroll))
        value_bets.extend(self.check_double_chance(prediction, odds_data, bankroll))

        if ou_odds:
            value_bets.extend(self.check_totals(prediction, ou_odds, bankroll))
        else:
            value_bets.extend(self.check_totals_from_xg(prediction, odds_data, bankroll))

        value_bets.sort(key=lambda x: x.value_percentage, reverse=True)
        return value_bets

    # ── 1X2 ─────────────────────────────────────

    def _check_1x2(self, prediction, odds_data, bankroll: float) -> List[ValueBet]:
        value_bets = []
        outcomes = {
            '1': ('Home Win', prediction.prob_home_win, odds_data.odds_1),
            'X': ('Draw', prediction.prob_draw, odds_data.odds_x),
            '2': ('Away Win', prediction.prob_away_win, odds_data.odds_2),
        }
        for bet_type, (name, model_prob, odds_dict) in outcomes.items():
            best_bk, best_odds = self._find_best_odds(odds_dict)
            if best_odds <= 1.0:
                continue
            market_prob = 1.0 / best_odds
            value = model_prob - market_prob
            if value < self.min_value:
                continue
            ev = (model_prob * best_odds) - 1.0
            kelly = self._kelly(model_prob, best_odds)
            selection = prediction.home_team if bet_type == '1' else (
                prediction.away_team if bet_type == '2' else 'Draw')
            value_bets.append(ValueBet(
                home_team=prediction.home_team, away_team=prediction.away_team,
                league=prediction.league, match_datetime=prediction.match_date,
                bet_type=bet_type, selection=selection,
                model_probability=model_prob, market_probability=market_prob,
                best_odds=best_odds, bookmaker=best_bk,
                value_percentage=value, expected_value=ev,
                kelly_stake=bankroll * kelly * self.kelly_fraction,
                confidence=self._get_confidence(value, '1x2'),
                odds_timestamp=datetime.now().isoformat()))
        return value_bets

    # ── DOUBLE CHANCE ───────────────────────────

    def check_double_chance(self, prediction, odds_data,
                            bankroll: float = 1000.0) -> List[ValueBet]:
        value_bets = []
        dc_probs = {
            '1X': prediction.prob_home_win + prediction.prob_draw,
            'X2': prediction.prob_draw + prediction.prob_away_win,
            '12': prediction.prob_home_win + prediction.prob_away_win,
        }
        dc_labels = {
            '1X': f'{prediction.home_team} or Draw',
            'X2': f'Draw or {prediction.away_team}',
            '12': f'{prediction.home_team} or {prediction.away_team}',
        }

        dc_odds_map = {}
        for attr, key in [('odds_dc_1x', '1X'), ('odds_dc_x2', 'X2'), ('odds_dc_12', '12')]:
            val = getattr(odds_data, attr, None)
            if val:
                dc_odds_map[key] = val
        if not dc_odds_map:
            dc_odds_map = self._derive_dc_odds(odds_data)

        for bt, model_prob in dc_probs.items():
            odds_dict = dc_odds_map.get(bt, {})
            if not odds_dict:
                continue
            best_bk, best_odds = self._find_best_odds(odds_dict)
            if best_odds <= 1.0:
                continue
            market_prob = 1.0 / best_odds
            value = model_prob - market_prob
            if value < self.dc_threshold:
                continue
            ev = (model_prob * best_odds) - 1.0
            kelly = self._kelly(model_prob, best_odds)
            value_bets.append(ValueBet(
                home_team=prediction.home_team, away_team=prediction.away_team,
                league=prediction.league, match_datetime=prediction.match_date,
                bet_type=bt, selection=dc_labels[bt],
                model_probability=model_prob, market_probability=market_prob,
                best_odds=best_odds, bookmaker=best_bk,
                value_percentage=value, expected_value=ev,
                kelly_stake=bankroll * kelly * self.kelly_fraction,
                confidence=self._get_confidence(value, 'dc'),
                odds_timestamp=datetime.now().isoformat()))
        return value_bets

    def _derive_dc_odds(self, odds_data) -> Dict:
        result = {}
        margin = 0.05
        try:
            b1 = max(odds_data.odds_1.values()) if odds_data.odds_1 else 0
            bx = max(odds_data.odds_x.values()) if odds_data.odds_x else 0
            b2 = max(odds_data.odds_2.values()) if odds_data.odds_2 else 0
        except (AttributeError, ValueError):
            return result
        if b1 <= 1 or bx <= 1 or b2 <= 1:
            return result
        p1, px, p2 = 1/b1, 1/bx, 1/b2
        for key, prob_sum in [('1X', p1+px), ('X2', px+p2), ('12', p1+p2)]:
            if prob_sum > 0:
                dc = 1.0 / (prob_sum * (1 + margin))
                if dc > 1.0:
                    result[key] = {'derived': dc}
        return result

    # ── OVER / UNDER ────────────────────────────

    def check_totals(self, prediction, ou_odds: Dict,
                     bankroll: float = 1000.0) -> List[ValueBet]:
        value_bets = []
        line = ou_odds.get('line', _OU_LINE)
        over_prob, under_prob = self._poisson_ou(
            prediction.expected_home_goals, prediction.expected_away_goals, line)

        for label, prob, odds_dict in [
            (f'Over_{line}', over_prob, ou_odds.get('over_odds', {})),
            (f'Under_{line}', under_prob, ou_odds.get('under_odds', {})),
        ]:
            if not odds_dict:
                continue
            best_bk, best_odds = self._find_best_odds(odds_dict)
            if best_odds <= 1.0:
                continue
            market_prob = 1.0 / best_odds
            value = prob - market_prob
            if value < self.ou_threshold:
                continue
            ev = (prob * best_odds) - 1.0
            kelly = self._kelly(prob, best_odds)
            value_bets.append(ValueBet(
                home_team=prediction.home_team, away_team=prediction.away_team,
                league=prediction.league, match_datetime=prediction.match_date,
                bet_type=label, selection=label.replace('_', ' ') + ' Goals',
                model_probability=prob, market_probability=market_prob,
                best_odds=best_odds, bookmaker=best_bk,
                value_percentage=value, expected_value=ev,
                kelly_stake=bankroll * kelly * self.kelly_fraction,
                confidence=self._get_confidence(value, 'ou'),
                odds_timestamp=datetime.now().isoformat()))
        return value_bets

    def check_totals_from_xg(self, prediction, odds_data,
                              bankroll: float = 1000.0) -> List[ValueBet]:
        if not hasattr(odds_data, 'odds_over') or not odds_data.odds_over:
            return []
        return self.check_totals(prediction, {
            'line': getattr(odds_data, 'ou_line', _OU_LINE),
            'over_odds': getattr(odds_data, 'odds_over', {}),
            'under_odds': getattr(odds_data, 'odds_under', {}),
        }, bankroll)

    def _poisson_ou(self, xg_h: float, xg_a: float, line: float) -> Tuple[float, float]:
        mg = self.max_goals
        over = under = exact = 0.0
        for i in range(mg + 1):
            for j in range(mg + 1):
                p = poisson.pmf(i, max(xg_h, 0.01)) * poisson.pmf(j, max(xg_a, 0.01))
                t = i + j
                if t > line:
                    over += p
                elif t < line:
                    under += p
                else:
                    exact += p
        if line == int(line):
            over += exact * 0.5
            under += exact * 0.5
        total = over + under
        return (over / total, under / total) if total > 0 else (0.5, 0.5)

    # ── BAYESIAN CONFIDENCE ─────────────────────

    def _calibrate_confidence(self, perf: Dict):
        total = perf.get('total_bets', 0)
        if total < 30:
            return
        high_wr = perf.get('high_conf_win_rate')
        med_wr = perf.get('medium_conf_win_rate')
        roi = perf.get('roi_percent', 0)

        if high_wr is not None:
            if high_wr < 45:
                self._base_thresholds['high'] = min(0.15, self._base_thresholds['high'] * 1.2)
            elif high_wr > 60:
                self._base_thresholds['high'] = max(0.08, self._base_thresholds['high'] * 0.9)
        if med_wr is not None:
            if med_wr < 40:
                self._base_thresholds['medium'] = min(0.08, self._base_thresholds['medium'] * 1.2)
            elif med_wr > 55:
                self._base_thresholds['medium'] = max(0.04, self._base_thresholds['medium'] * 0.9)
        if roi < -5:
            for k in self._base_thresholds:
                self._base_thresholds[k] *= 1.1
        elif roi > 10:
            for k in self._base_thresholds:
                self._base_thresholds[k] *= 0.95

    def _get_confidence(self, value: float, market: str = '1x2') -> str:
        t = dict(self._base_thresholds)
        if market == 'ou':
            t = {k: v * 0.85 for k, v in t.items()}
        elif market == 'dc':
            t = {k: v * 0.7 for k, v in t.items()}
        if value >= t['high']:
            return 'high'
        elif value >= t['medium']:
            return 'medium'
        elif value >= t['low']:
            return 'low'
        return 'none'

    # ── CLV ──────────────────────────────────────

    @staticmethod
    def calculate_clv(opening_odds: float, closing_odds: float) -> float:
        if opening_odds <= 1.0 or closing_odds <= 1.0:
            return 0.0
        # CLV: positive = we beat the closing line (got better odds)
        closing_imp = 1.0 / closing_odds
        opening_imp = 1.0 / opening_odds
        return (closing_imp - opening_imp) / opening_imp

    @staticmethod
    def update_closing_odds(bet: ValueBet, closing_odds: float) -> ValueBet:
        bet.closing_odds = closing_odds
        bet.clv = ValueEngine.calculate_clv(bet.best_odds, closing_odds)
        return bet

    # ── CORRELATED BETS ─────────────────────────

    def detect_correlations(self, value_bets: List[ValueBet]) -> List[Dict]:
        correlations = []
        matches = {}
        for b in value_bets:
            key = f"{b.home_team}_vs_{b.away_team}"
            matches.setdefault(key, []).append(b)

        for mk, bets in matches.items():
            if len(bets) < 2:
                continue
            types = {b.bet_type for b in bets}

            # Home + Over → dominant home win expected
            if '1' in types and any('Over' in t for t in types):
                hb = next(b for b in bets if b.bet_type == '1')
                ob = next(b for b in bets if 'Over' in b.bet_type)
                correlations.append({
                    'match': mk, 'type': 'home_win_over',
                    'description': f'Home Win + Over → Strong home performance',
                    'combined_value': hb.value_percentage + ob.value_percentage,
                    'bets': [hb, ob],
                    'strength': 'strong' if hb.value_percentage > 0.08 else 'moderate'})

            # Away + Over
            if '2' in types and any('Over' in t for t in types):
                ab = next(b for b in bets if b.bet_type == '2')
                ob = next(b for b in bets if 'Over' in b.bet_type)
                correlations.append({
                    'match': mk, 'type': 'away_win_over',
                    'description': 'Away Win + Over → Open attacking game',
                    'combined_value': ab.value_percentage + ob.value_percentage,
                    'bets': [ab, ob], 'strength': 'moderate'})

            # Draw + Under
            if 'X' in types and any('Under' in t for t in types):
                db = next(b for b in bets if b.bet_type == 'X')
                ub = next(b for b in bets if 'Under' in b.bet_type)
                correlations.append({
                    'match': mk, 'type': 'draw_under',
                    'description': 'Draw + Under → Defensive stalemate',
                    'combined_value': db.value_percentage + ub.value_percentage,
                    'bets': [db, ub], 'strength': 'strong'})

        return correlations

    # ── REPORT ───────────────────────────────────

    def format_report(self, value_bets: List[ValueBet],
                      correlations: Optional[List[Dict]] = None) -> str:
        if not value_bets:
            return "Keine Value-Bets gefunden."
        lines = [f"\nGefundene Value-Bets: {len(value_bets)}\n", "-" * 80]

        by_market = {'1X2': [], 'DC': [], 'O/U': []}
        for b in value_bets:
            if b.bet_type in ('1', 'X', '2'):
                by_market['1X2'].append(b)
            elif b.bet_type in ('1X', 'X2', '12'):
                by_market['DC'].append(b)
            else:
                by_market['O/U'].append(b)

        for name, bets in by_market.items():
            if not bets:
                continue
            lines.append(f"\n📊 {name}:")
            for i, b in enumerate(bets[:5], 1):
                lines.append(f"  {i}. {b.home_team} vs {b.away_team}")
                lines.append(f"     {b.selection} @ {b.best_odds:.2f}")
                lines.append(f"     Model: {b.model_probability:.1%} | Market: {b.market_probability:.1%}")
                lines.append(f"     Value: {b.value_percentage:.1%} | EV: {b.roi:+.1f}%")
                lines.append(f"     Kelly: {b.kelly_stake:.1f}€ | Conf: {b.confidence.upper()}")

        if correlations:
            lines.append(f"\n🔗 Korrelierte Bets: {len(correlations)}")
            for c in correlations:
                lines.append(f"  • {c['description']} [{c['strength']}]")
                lines.append(f"    Combined Value: {c['combined_value']:.1%}")
        lines.append("-" * 80)
        return "\n".join(lines)

    # ── HELPERS ──────────────────────────────────

    def _find_best_odds(self, odds: Dict[str, float]) -> Tuple[str, float]:
        if not odds:
            return ("unknown", 0.0)
        return max(odds.items(), key=lambda x: x[1])

    def _kelly(self, prob: float, odds: float) -> float:
        if odds <= 1.0:
            return 0.0
        b = odds - 1
        k = (b * prob - (1 - prob)) / b
        return max(0.0, k)

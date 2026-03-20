"""Shared helpers for over/under player props across sports."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import NormalDist, mean
from typing import Dict, Iterable, List, Optional, Tuple

from .runtime_utils import ensure_parent, safe_float


DEFAULT_STD_BY_MARKET = {
    'player_points': 6.5,
    'player_rebounds': 3.2,
    'player_assists': 2.6,
    'player_threes': 1.4,
    'player_pass_yds': 48.0,
    'player_pass_tds': 0.9,
    'player_rush_yds': 21.0,
    'player_reception_yds': 24.0,
    'player_receptions': 2.1,
    'player_shots_on_target': 0.9,
    'player_shots': 1.5,
    'player_assists_soccer': 0.35,
    'player_passes': 11.0,
    'player_tackles': 1.8,
    'player_cards': 0.45,
}

MARKET_ALIASES = {
    'player_points': 'player_points',
    'player_rebounds': 'player_rebounds',
    'player_assists': 'player_assists',
    'player_threes': 'player_threes',
    'player_3pts': 'player_threes',
    'player_pass_yds': 'player_pass_yds',
    'player_pass_tds': 'player_pass_tds',
    'player_rush_yds': 'player_rush_yds',
    'player_reception_yds': 'player_reception_yds',
    'player_receptions': 'player_receptions',
    'player_shots_on_target': 'player_shots_on_target',
    'player_shots': 'player_shots',
    'player_assists_soccer': 'player_assists_soccer',
    'player_passes': 'player_passes',
    'player_tackles': 'player_tackles',
    'player_cards': 'player_cards',
}


@dataclass
class PropOption:
    bookmaker: str
    odds: float
    line: Optional[float] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PlayerPropCandidate:
    sport: str
    league: str
    event_id: str
    home_team: str
    away_team: str
    match_date: str
    market: str
    player_name: str
    line: float
    selection: str
    prop_side: str
    odds: float
    bookmaker: str
    bookmaker_options: List[Dict]
    model_prob: float
    market_prob: float
    value_percentage: float
    expected_value: float
    raw_kelly_stake: float
    confidence: str

    def to_tracking_payload(self, execution_mode: str, model_version: str, calibration_version: str, feature_version: str = 'v4-props') -> Dict:
        return {
            'execution_mode': execution_mode,
            'league': self.league,
            'match_id': self.event_id,
            'event_id': self.event_id,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'match_date': self.match_date,
            'bet_type': self.market,
            'market': self.market,
            'selection': self.selection,
            'line': self.line,
            'odds': self.odds,
            'opening_odds': self.odds,
            'bookmaker': self.bookmaker,
            'bookmaker_options': self.bookmaker_options,
            'model_prob': self.model_prob,
            'market_prob': self.market_prob,
            'value_percentage': self.value_percentage,
            'expected_value': self.expected_value,
            'raw_kelly_stake': self.raw_kelly_stake,
            'kelly_stake': self.raw_kelly_stake,
            'confidence': self.confidence,
            'stake_multiplier': 1.0,
            'model_version': model_version,
            'feature_set_version': feature_version,
            'data_version': feature_version,
            'thresholds_version': feature_version,
            'calibration_version': calibration_version,
            'player_name': self.player_name,
            'prop_side': self.prop_side,
        }


def normalize_market_key(value: str) -> str:
    return MARKET_ALIASES.get(str(value or '').strip().lower(), str(value or '').strip().lower())


def load_prop_priors(path: Path, sample_path: Optional[Path] = None) -> Dict:
    candidates = [path]
    if sample_path:
        candidates.append(sample_path)
    for candidate in candidates:
        if candidate and candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                continue
    return {'players': {}}


def _find_player_entry(priors: Dict, player_name: str) -> Dict:
    players = priors.get('players', {}) if isinstance(priors, dict) else {}
    if player_name in players:
        return players[player_name]
    norm = player_name.strip().lower()
    for name, entry in players.items():
        if str(name).strip().lower() == norm:
            return entry
    return {}


def prior_probability_over(priors: Dict, player_name: str, market: str, line: float) -> Optional[float]:
    entry = _find_player_entry(priors, player_name)
    if not entry:
        return None
    market = normalize_market_key(market)
    market_entry = entry.get(market) or entry.get(market.replace('player_assists_soccer', 'player_assists'))
    if not isinstance(market_entry, dict):
        return None
    mean_value = safe_float(market_entry.get('mean'))
    if mean_value is None:
        prob = safe_float(market_entry.get('probability_over'))
        return prob if prob is not None else None
    std_value = safe_float(market_entry.get('std')) or DEFAULT_STD_BY_MARKET.get(market, 1.0)
    std_value = max(std_value, 0.1)
    return max(0.02, min(0.98, 1.0 - NormalDist(mu=mean_value, sigma=std_value).cdf(line)))


def decimal_implied_prob(odds: float) -> float:
    odds = safe_float(odds, 0.0) or 0.0
    if odds <= 1.0:
        return 0.0
    return 1.0 / odds


def no_vig_over_probability(over_options: Iterable[Dict], under_options: Iterable[Dict]) -> float:
    over_map = {o.get('bookmaker'): safe_float(o.get('odds')) for o in over_options if o.get('bookmaker')}
    under_map = {o.get('bookmaker'): safe_float(o.get('odds')) for o in under_options if o.get('bookmaker')}
    paired = []
    for bookmaker in set(over_map) & set(under_map):
        over_odds = over_map.get(bookmaker)
        under_odds = under_map.get(bookmaker)
        if not over_odds or not under_odds or over_odds <= 1 or under_odds <= 1:
            continue
        p_over = 1.0 / over_odds
        p_under = 1.0 / under_odds
        total = p_over + p_under
        if total > 0:
            paired.append(p_over / total)
    if paired:
        return max(0.02, min(0.98, mean(paired)))
    over_odds = mean([safe_float(o.get('odds'), 0.0) or 0.0 for o in over_options]) if list(over_options) else 0.0
    under_odds = mean([safe_float(o.get('odds'), 0.0) or 0.0 for o in under_options]) if list(under_options) else 0.0
    if over_odds > 1 and under_odds > 1:
        p_over = 1.0 / over_odds
        p_under = 1.0 / under_odds
        total = p_over + p_under
        if total > 0:
            return max(0.02, min(0.98, p_over / total))
    return 0.5


def combine_probabilities(consensus_over: float, prior_over: Optional[float], prior_weight: float = 0.25) -> float:
    if prior_over is None:
        return consensus_over
    prior_weight = max(0.0, min(0.8, prior_weight))
    model_prob = (1 - prior_weight) * consensus_over + prior_weight * prior_over
    return max(0.02, min(0.98, model_prob))


def kelly_stake(probability: float, odds: float, bankroll: float, fraction: float, max_bet_pct: float) -> float:
    if odds <= 1.0:
        return 0.0
    edge = (odds - 1.0) * probability - (1.0 - probability)
    if edge <= 0:
        return 0.0
    full_kelly = edge / (odds - 1.0)
    stake = bankroll * max(0.0, full_kelly) * max(0.0, fraction)
    return round(min(stake, bankroll * max_bet_pct), 2)


def confidence_label(expected_value: float, model_prob: float, prior_available: bool) -> str:
    if expected_value >= 0.10 and model_prob >= 0.58 and prior_available:
        return 'high'
    if expected_value >= 0.06 and model_prob >= 0.54:
        return 'medium'
    return 'low'


def summarize_options(options: Iterable[Dict]) -> List[Dict]:
    cleaned = []
    for row in options:
        bookmaker = row.get('bookmaker')
        odds = safe_float(row.get('odds'))
        line = safe_float(row.get('line'))
        if not bookmaker or not odds:
            continue
        cleaned.append({'bookmaker': bookmaker, 'odds': odds, 'line': line})
    return sorted(cleaned, key=lambda x: x['odds'], reverse=True)


def analyze_over_under_group(
    *,
    sport: str,
    league: str,
    event_id: str,
    home_team: str,
    away_team: str,
    match_date: str,
    market: str,
    player_name: str,
    line: float,
    over_options: Iterable[Dict],
    under_options: Iterable[Dict],
    priors: Dict,
    threshold: float,
    bankroll: float,
    kelly_fraction: float,
    max_bet_pct: float,
    prior_weight: float = 0.25,
) -> Optional[PlayerPropCandidate]:
    market = normalize_market_key(market)
    over_options = summarize_options(over_options)
    under_options = summarize_options(under_options)
    if not over_options or not under_options:
        return None
    consensus_over = no_vig_over_probability(over_options, under_options)
    prior_over = prior_probability_over(priors, player_name, market, line)
    model_over = combine_probabilities(consensus_over, prior_over, prior_weight=prior_weight)
    model_under = 1.0 - model_over

    best_over = over_options[0]
    best_under = under_options[0]
    over_ev = model_over * best_over['odds'] - 1.0
    under_ev = model_under * best_under['odds'] - 1.0
    prior_available = prior_over is not None

    if over_ev >= under_ev:
        if over_ev < threshold:
            return None
        stake = kelly_stake(model_over, best_over['odds'], bankroll, kelly_fraction, max_bet_pct)
        if stake <= 0:
            return None
        return PlayerPropCandidate(
            sport=sport,
            league=league,
            event_id=event_id,
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            market=market,
            player_name=player_name,
            line=line,
            selection=f'{player_name} Over {line}',
            prop_side='over',
            odds=best_over['odds'],
            bookmaker=best_over['bookmaker'],
            bookmaker_options=over_options,
            model_prob=model_over,
            market_prob=decimal_implied_prob(best_over['odds']),
            value_percentage=round(over_ev, 4),
            expected_value=round(over_ev, 4),
            raw_kelly_stake=stake,
            confidence=confidence_label(over_ev, model_over, prior_available),
        )
    if under_ev < threshold:
        return None
    stake = kelly_stake(model_under, best_under['odds'], bankroll, kelly_fraction, max_bet_pct)
    if stake <= 0:
        return None
    return PlayerPropCandidate(
        sport=sport,
        league=league,
        event_id=event_id,
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        market=market,
        player_name=player_name,
        line=line,
        selection=f'{player_name} Under {line}',
        prop_side='under',
        odds=best_under['odds'],
        bookmaker=best_under['bookmaker'],
        bookmaker_options=under_options,
        model_prob=model_under,
        market_prob=decimal_implied_prob(best_under['odds']),
        value_percentage=round(under_ev, 4),
        expected_value=round(under_ev, 4),
        raw_kelly_stake=stake,
        confidence=confidence_label(under_ev, model_under, prior_available),
    )

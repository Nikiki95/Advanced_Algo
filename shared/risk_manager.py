"""Portfolio-level stake controls and correlated-bet limits."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class RiskDecision:
    approved: bool
    status: str
    approved_stake: float
    stake_multiplier: float
    reasons: List[str]
    exposure_before: Dict
    exposure_after: Dict

    def to_dict(self) -> Dict:
        return asdict(self)


class PortfolioRiskManager:
    def __init__(self,
                 bankroll: float = 1000.0,
                 max_daily_risk_pct: float = 0.12,
                 max_sport_risk_pct: float = 0.08,
                 max_league_risk_pct: float = 0.05,
                 max_event_risk_pct: float = 0.03,
                 max_team_risk_pct: float = 0.04,
                 max_player_risk_pct: float = 0.025):
        self.bankroll = bankroll
        self.max_daily_risk = bankroll * max_daily_risk_pct
        self.max_sport_risk = bankroll * max_sport_risk_pct
        self.max_league_risk = bankroll * max_league_risk_pct
        self.max_event_risk = bankroll * max_event_risk_pct
        self.max_team_risk = bankroll * max_team_risk_pct
        self.max_player_risk = bankroll * max_player_risk_pct

    def _event_key(self, bet: Dict) -> str:
        return f"{bet.get('sport')}|{bet.get('home_team')}|{bet.get('away_team')}|{str(bet.get('match_date', ''))[:19]}"

    def _exposure(self, bets: List[Dict]) -> Dict:
        exposure = {
            'total': 0.0,
            'by_sport': {},
            'by_league': {},
            'by_event': {},
            'by_team': {},
            'by_player': {},
        }
        for bet in bets:
            stake = float(bet.get('kelly_stake') or bet.get('approved_stake') or 0)
            if stake <= 0:
                continue
            sport = bet.get('sport', 'unknown')
            league = bet.get('league', 'unknown')
            event = self._event_key(bet)
            exposure['total'] += stake
            exposure['by_sport'][sport] = exposure['by_sport'].get(sport, 0.0) + stake
            exposure['by_league'][league] = exposure['by_league'].get(league, 0.0) + stake
            exposure['by_event'][event] = exposure['by_event'].get(event, 0.0) + stake
            for team in [bet.get('home_team'), bet.get('away_team')]:
                if team:
                    exposure['by_team'][team] = exposure['by_team'].get(team, 0.0) + stake
            if bet.get('player_name'):
                exposure['by_player'][bet.get('player_name')] = exposure['by_player'].get(bet.get('player_name'), 0.0) + stake
        return exposure

    def evaluate_bet(self, candidate: Dict, active_bets: List[Dict]) -> RiskDecision:
        before = self._exposure(active_bets)
        proposed = float(candidate.get('kelly_stake') or 0)
        reasons: List[str] = []
        multiplier = 1.0
        event_key = self._event_key(candidate)
        sport = candidate.get('sport', 'unknown')
        league = candidate.get('league', 'unknown')

        same_event = before['by_event'].get(event_key, 0.0)
        if same_event > 0:
            multiplier *= 0.65
            reasons.append('same-event exposure already exists')

        team_exposure = max(before['by_team'].get(candidate.get('home_team'), 0.0),
                            before['by_team'].get(candidate.get('away_team'), 0.0))
        player_name = candidate.get('player_name')
        player_exposure = before['by_player'].get(player_name, 0.0) if player_name else 0.0
        if team_exposure > self.max_team_risk * 0.75:
            multiplier *= 0.75
            reasons.append('team exposure is elevated')

        if player_name and player_exposure > self.max_player_risk * 0.75:
            multiplier *= 0.7
            reasons.append('player exposure is elevated')

        approved_stake = proposed * multiplier
        total_after = before['total'] + approved_stake
        sport_after = before['by_sport'].get(sport, 0.0) + approved_stake
        league_after = before['by_league'].get(league, 0.0) + approved_stake
        event_after = same_event + approved_stake
        team_after = team_exposure + approved_stake
        player_after = player_exposure + approved_stake

        hard_block = False
        if total_after > self.max_daily_risk:
            hard_block = True
            reasons.append('daily risk cap exceeded')
        if sport_after > self.max_sport_risk:
            hard_block = True
            reasons.append('sport risk cap exceeded')
        if league_after > self.max_league_risk:
            hard_block = True
            reasons.append('league risk cap exceeded')
        if event_after > self.max_event_risk:
            hard_block = True
            reasons.append('event risk cap exceeded')
        if team_after > self.max_team_risk:
            hard_block = True
            reasons.append('team risk cap exceeded')
        if player_name and player_after > self.max_player_risk:
            hard_block = True
            reasons.append('player risk cap exceeded')

        status = 'approved'
        if hard_block or approved_stake <= 0:
            status = 'rejected'
            approved_stake = 0.0
            multiplier = 0.0
        elif multiplier < 0.999:
            status = 'reduced'

        after = {
            'total': before['total'] + approved_stake,
            'sport': sport_after if approved_stake else before['by_sport'].get(sport, 0.0),
            'league': league_after if approved_stake else before['by_league'].get(league, 0.0),
            'event': event_after if approved_stake else same_event,
            'team': team_after if approved_stake else team_exposure,
            'player': player_after if approved_stake else player_exposure,
        }
        return RiskDecision(status != 'rejected', status, round(approved_stake, 2), round(multiplier, 3), reasons, before, after)

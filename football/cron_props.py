#!/usr/bin/env python3
"""Football player props runner for domestic leagues plus Champions/Europa/Conference League."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent / 'src') not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from shared.calibration import MarketCalibration
from shared.closing_line import ClosingLineManager
from shared.feedback_loop import UniversalBetTracker
from shared.player_props import analyze_over_under_group, load_prop_priors
from shared.risk_manager import PortfolioRiskManager
from shared.runtime_utils import canonical_event_key, load_env, now_iso, safe_float
from football.config import (
    PLAYER_PROP_KELLY_FRACTION,
    PLAYER_PROP_MARKETS,
    PLAYER_PROP_MAX_BET_PERCENT,
    PLAYER_PROP_PRIOR_WEIGHT,
    PLAYER_PROP_VALUE_THRESHOLD,
)
from scraper.player_props_scraper import FootballPlayerPropsScraper

load_env()

try:
    from notifications.telegram import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False
    TelegramNotifier = None

DEFAULT_SCOPES = ['D1', 'D2', 'E0', 'SP1', 'I1', 'F1', 'P1', 'N1', 'UCL', 'UEL', 'UECL']


class FootballPropsCronRunner:
    def __init__(self, execution_mode: str = 'live'):
        self.execution_mode = execution_mode
        self.scraper = FootballPlayerPropsScraper()
        self.tracker = UniversalBetTracker()
        self.calibration = MarketCalibration()
        self.closing = ClosingLineManager()
        self.risk = PortfolioRiskManager(bankroll=1000.0)
        self.notifier = TelegramNotifier() if TELEGRAM_AVAILABLE else None
        self.priors = load_prop_priors(
            Path(__file__).resolve().parent / 'models' / 'player_props_priors.json',
            Path(__file__).resolve().parent / 'models' / 'player_props_priors.sample.json',
        )

    def _group_rows(self, rows):
        grouped = defaultdict(lambda: {'over': [], 'under': []})
        for row in rows:
            market = row.get('market')
            player_name = row.get('player_name')
            line = safe_float(row.get('line'))
            side = row.get('side')
            if not market or not player_name or line is None or side not in ('over', 'under'):
                continue
            grouped[(market, player_name, line)][side].append(
                {'bookmaker': row.get('bookmaker'), 'odds': row.get('odds'), 'line': row.get('line')}
            )
        return grouped

    def _record_snapshots(self, event):
        rows = []
        for row in event.get('rows', []):
            rows.append({
                'market': row.get('market'),
                'selection': f"{row.get('player_name')} {row.get('side')} {row.get('line')}",
                'bookmaker': row.get('bookmaker'),
                'odds': row.get('odds'),
                'line': row.get('line'),
            })
        self.closing.record_candidates('football', event['home_team'], event['away_team'], event.get('match_date'), event['event_id'], rows)

    def run(self, scopes=None, markets=None, max_events_per_scope=None):
        scopes = scopes or list(DEFAULT_SCOPES)
        events = self.scraper.fetch_scope_props(scopes=scopes, markets=markets or list(PLAYER_PROP_MARKETS), max_events_per_scope=max_events_per_scope)
        active_cache = self.tracker.get_active_bets(sport='football')
        alerts, tracked = [], []
        for event in events:
            self._record_snapshots(event)
            for (market, player_name, line), options in self._group_rows(event.get('rows', [])).items():
                candidate = analyze_over_under_group(
                    sport='football',
                    league=event.get('league', 'football'),
                    event_id=canonical_event_key('football', event['home_team'], event['away_team'], event.get('match_date')),
                    home_team=event['home_team'],
                    away_team=event['away_team'],
                    match_date=event.get('match_date'),
                    market=market,
                    player_name=player_name,
                    line=line,
                    over_options=options['over'],
                    under_options=options['under'],
                    priors=self.priors,
                    threshold=PLAYER_PROP_VALUE_THRESHOLD,
                    bankroll=1000.0,
                    kelly_fraction=PLAYER_PROP_KELLY_FRACTION,
                    max_bet_pct=PLAYER_PROP_MAX_BET_PERCENT,
                    prior_weight=PLAYER_PROP_PRIOR_WEIGHT,
                )
                if not candidate:
                    continue
                calibration = self.calibration.adjust_bet('football', candidate.market, candidate.raw_kelly_stake, candidate.value_percentage, candidate.confidence)
                payload = candidate.to_tracking_payload(self.execution_mode, 'football-props-consensus-v6', self.calibration.profile.get('version', 'v4-props'))
                payload['kelly_stake'] = calibration['adjusted_stake']
                payload['confidence'] = calibration['adjusted_confidence']
                payload['stake_multiplier'] = calibration['stake_multiplier']
                payload['event_id'] = canonical_event_key('football', event['home_team'], event['away_team'], event.get('match_date'))
                dedupe_key = (payload['event_id'], payload['market'], payload['selection'])
                if dedupe_key in {(b.get('event_id'), b.get('market'), b.get('selection')) for b in active_cache}:
                    continue
                risk = self.risk.evaluate_bet({'sport': 'football', **payload}, active_cache)
                if not risk.approved:
                    continue
                payload['risk_status'] = risk.status
                payload['risk_reasons'] = risk.reasons
                payload['kelly_stake'] = risk.approved_stake
                self.tracker.place_bet(payload, sport='football')
                active_cache.append({'sport': 'football', **payload})
                tracked.append(payload)
                if payload['confidence'] in ('high', 'medium'):
                    alerts.append(payload)
        result = {'timestamp': now_iso(), 'execution_mode': self.execution_mode, 'scopes': scopes, 'events_checked': len(events), 'bets_tracked': len(tracked), 'alerts': min(5, len(alerts))}
        print(json.dumps(result, indent=2))
        return result


def main():
    parser = argparse.ArgumentParser(description='Football player props runner for domestic leagues plus Champions/Europa/Conference League.')
    parser.add_argument('--scopes', nargs='*', default=None, help='League/competition codes such as D1 D2 E0 SP1 I1 F1 P1 N1 UCL UEL UECL')
    parser.add_argument('--markets', nargs='*', default=None)
    parser.add_argument('--max-events-per-scope', type=int, default=None)
    parser.add_argument('--shadow', action='store_true')
    args = parser.parse_args()
    runner = FootballPropsCronRunner(execution_mode='shadow' if args.shadow else os.getenv('EXECUTION_MODE', 'live'))
    runner.run(scopes=args.scopes, markets=args.markets, max_events_per_scope=args.max_events_per_scope)


if __name__ == '__main__':
    main()

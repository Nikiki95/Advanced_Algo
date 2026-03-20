#!/usr/bin/env python3
"""Settle non-prop bets across sports using automatic and manual result sources."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from football.src.utils.result_fetcher import FootballDataFetcher
from shared.closing_line import ClosingLineManager
from shared.feedback_loop import UniversalBetTracker
from shared.runtime_utils import data_root, now_iso
from shared.player_name_matcher import normalize_team


class ManualTeamResultStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or data_root() / 'settlement' / 'manual'
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths_for_sport(self, sport: str) -> List[Path]:
        return [
            self.root / f'{sport}_team_results.json',
            self.root / f'{sport}_team_results.jsonl',
            self.root / 'all_team_results.json',
            self.root / 'all_team_results.jsonl',
        ]

    def _load_rows(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        if path.suffix == '.jsonl':
            rows = []
            for line in path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return rows
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict) and isinstance(payload.get('rows'), list):
            return [row for row in payload['rows'] if isinstance(row, dict)]
        return []

    def lookup(self, bet: Dict) -> Optional[Dict]:
        for path in self._paths_for_sport(str(bet.get('sport') or '')):
            for row in self._load_rows(path):
                if row.get('sport') and str(row.get('sport')).lower() != str(bet.get('sport')).lower():
                    continue
                if row.get('event_id') and str(row.get('event_id')) == str(bet.get('event_id')):
                    return dict(row, source=f'manual:{path.name}')
                if normalize_team(row.get('home_team')) != normalize_team(bet.get('home_team')):
                    continue
                if normalize_team(row.get('away_team')) != normalize_team(bet.get('away_team')):
                    continue
                row_dt = _coerce_dt(row.get('match_date'))
                bet_dt = _coerce_dt(bet.get('match_date'))
                if row_dt and bet_dt and abs((row_dt - bet_dt).total_seconds()) > 36 * 3600:
                    continue
                return dict(row, source=f'manual:{path.name}')
        return None


def _coerce_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        try:
            dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
        except Exception:
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
                try:
                    dt = datetime.strptime(text[:19], fmt)
                    break
                except Exception:
                    dt = None
            if dt is None:
                return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ready(bet: Dict, settle_after_hours: float) -> bool:
    dt = _coerce_dt(bet.get('match_date'))
    if not dt:
        return False
    return datetime.now(timezone.utc) - dt >= timedelta(hours=settle_after_hours)


def _calc_team_outcome(bet: Dict, result: Dict) -> str:
    market = str(bet.get('market') or bet.get('bet_type') or '').lower()
    selection = str(bet.get('selection') or '')
    home_score = float(result.get('home_score', result.get('home_goals', 0)) or 0)
    away_score = float(result.get('away_score', result.get('away_goals', 0)) or 0)
    winner = str(result.get('winner') or '').lower()
    if not winner:
        winner = 'draw' if home_score == away_score else 'home' if home_score > away_score else 'away'

    if market in ('moneyline', 'h2h', '1x2', '1', 'x', '2'):
        bet_type = str(bet.get('bet_type') or '').upper()
        if bet_type in ('1', 'X', '2'):
            desired = {'1': 'home', 'X': 'draw', '2': 'away'}[bet_type]
        else:
            sel = selection.lower()
            desired = 'draw' if sel == 'draw' else 'home' if normalize_team(selection) == normalize_team(bet.get('home_team')) else 'away'
        return 'win' if desired == winner else 'loss'

    if market in ('dc', '1x', 'x2', '12') or str(bet.get('bet_type') or '').upper() in ('1X', 'X2', '12'):
        bet_type = str(bet.get('bet_type') or market).upper()
        if bet_type == '1X':
            return 'win' if winner in ('home', 'draw') else 'loss'
        if bet_type == 'X2':
            return 'win' if winner in ('away', 'draw') else 'loss'
        if bet_type == '12':
            return 'win' if winner in ('home', 'away') else 'loss'

    if market == 'spread':
        line = float(bet.get('line') or 0)
        sel = selection.lower()
        adjusted_home = home_score + (line if normalize_team(selection) == normalize_team(bet.get('home_team')) else 0)
        adjusted_away = away_score + (line if normalize_team(selection) == normalize_team(bet.get('away_team')) else 0)
        if adjusted_home == adjusted_away:
            return 'push'
        if normalize_team(selection) == normalize_team(bet.get('home_team')):
            return 'win' if adjusted_home > away_score else 'loss'
        return 'win' if adjusted_away > home_score else 'loss'

    if market in ('totals', 'ou') or selection.lower().startswith('over') or selection.lower().startswith('under'):
        line = float(bet.get('line') or _line_from_text(selection) or 0)
        total = home_score + away_score
        if selection.lower().startswith('over'):
            return 'win' if total > line else 'push' if total == line else 'loss'
        return 'win' if total < line else 'push' if total == line else 'loss'

    return 'loss'


def _line_from_text(selection: str) -> Optional[float]:
    import re
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)', selection or '')
    return float(m.group(1)) if m else None


def _calc_pnl(bet: Dict, outcome: str) -> float:
    stake = float(bet.get('kelly_stake') or 0)
    odds = float(bet.get('odds') or 0)
    if outcome == 'win':
        return round(stake * (odds - 1.0), 2)
    if outcome in ('push', 'void'):
        return 0.0
    return round(-stake, 2)


class TeamSettlementRunner:
    def __init__(self):
        self.tracker = UniversalBetTracker()
        self.manual = ManualTeamResultStore()
        self.closing = ClosingLineManager()
        self.football_fetcher = FootballDataFetcher()
        self.unresolved_root = data_root() / 'settlement' / 'unresolved'
        self.unresolved_root.mkdir(parents=True, exist_ok=True)

    def settle(self, sport: str, execution_mode: Optional[str] = None, settle_after_hours: float = 4.0,
               manual_only: bool = False, max_bets: Optional[int] = None, leagues: Optional[List[str]] = None) -> Dict:
        active = self.tracker.get_active_bets(sport=sport, execution_mode=execution_mode)
        if leagues:
            wanted = {str(x).upper() for x in leagues}
            active = [b for b in active if str(b.get('league') or '').upper() in wanted]
        if max_bets is not None:
            active = active[:max_bets]
        settled, unresolved = [], []
        for bet in active:
            if bet.get('player_name'):
                continue
            if not _ready(bet, settle_after_hours):
                continue
            resolved = None
            if sport == 'football' and not manual_only:
                resolved = self.football_fetcher.match_result(bet.get('home_team', ''), bet.get('away_team', ''), bet.get('match_date', ''), bet.get('league', ''))
                if resolved:
                    resolved = {
                        'home_score': resolved.get('home_goals'),
                        'away_score': resolved.get('away_goals'),
                        'winner': 'home' if resolved.get('result') == 'H' else 'away' if resolved.get('result') == 'A' else 'draw',
                        'source': resolved.get('source', 'auto:football-results'),
                        'event_reference': resolved.get('event_reference'),
                    }
            if not resolved:
                resolved = self.manual.lookup(bet)
            if not resolved:
                unresolved.append({
                    'bet_id': bet.get('bet_id'),
                    'sport': sport,
                    'league': bet.get('league'),
                    'event_id': bet.get('event_id'),
                    'home_team': bet.get('home_team'),
                    'away_team': bet.get('away_team'),
                    'match_date': bet.get('match_date'),
                    'checked_at': now_iso(),
                })
                continue
            outcome = _calc_team_outcome(bet, resolved)
            pnl = _calc_pnl(bet, outcome)
            closing = self.closing.lookup_closing_odds(bet) or {}
            details = {
                'settlement_source': resolved.get('source'),
                'settlement_event_reference': resolved.get('event_reference'),
                'settlement_notes': resolved.get('notes'),
                'home_score': resolved.get('home_score'),
                'away_score': resolved.get('away_score'),
                'winner': resolved.get('winner'),
            }
            ok = self.tracker.settle_bet(bet['bet_id'], outcome, pnl, closing.get('closing_odds'), closing.get('closing_bookmaker'), settlement_details=details)
            if ok:
                settled.append({'bet_id': bet.get('bet_id'), 'result': outcome, 'profit_loss': pnl})
        if unresolved:
            out = self.unresolved_root / f'{sport}_team_unresolved.jsonl'
            with out.open('a', encoding='utf-8') as f:
                for row in unresolved:
                    f.write(json.dumps(row) + '\n')
        return {
            'timestamp': now_iso(),
            'sport': sport,
            'settled_count': len(settled),
            'unresolved_count': len(unresolved),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Settle non-prop bets across sports')
    parser.add_argument('--sport', choices=['football', 'nba', 'nfl', 'euroleague', 'tennis', 'all'], default='all')
    parser.add_argument('--execution-mode', choices=['live', 'shadow'], default=None)
    parser.add_argument('--settle-after-hours', type=float, default=4.0)
    parser.add_argument('--manual-only', action='store_true')
    parser.add_argument('--max-bets', type=int, default=None)
    parser.add_argument('--leagues', nargs='*', default=None)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    runner = TeamSettlementRunner()
    sports = ['football', 'nba', 'nfl', 'euroleague', 'tennis'] if args.sport == 'all' else [args.sport]
    results = [runner.settle(s, execution_mode=args.execution_mode, settle_after_hours=args.settle_after_hours, manual_only=args.manual_only, max_bets=args.max_bets, leagues=args.leagues) for s in sports]
    payload = {'timestamp': now_iso(), 'results': results}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for row in results:
            print(f"{row['sport']}: settled={row['settled_count']} unresolved={row['unresolved_count']}")


if __name__ == '__main__':
    main()

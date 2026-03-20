"""Player-prop settlement pipeline with manual-stat and API-Sports resolution."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .api_sports_client import APISportsClient
from .closing_line import ClosingLineManager
from .feedback_loop import UniversalBetTracker
from .runtime_utils import data_root, ensure_parent, load_env, now_iso, safe_float
from .player_name_matcher import normalize_person, normalize_team, normalize_text, person_match_score, team_match_score

load_env()


PROP_MARKETS_BY_SPORT = {
    'nba': {'player_points', 'player_rebounds', 'player_assists', 'player_threes'},
    'nfl': {'player_pass_yds', 'player_pass_tds', 'player_rush_yds', 'player_reception_yds', 'player_receptions'},
    'football': {'player_shots', 'player_shots_on_target', 'player_assists_soccer', 'player_passes', 'player_tackles', 'player_cards'},
}


@dataclass
class PropSettlementRecord:
    bet_id: str
    sport: str
    player_name: str
    market: str
    actual_value: float
    line: float
    result: str
    profit_loss: float
    source: str
    event_reference: Optional[str] = None
    raw_status: Optional[str] = None
    notes: Optional[str] = None


class ManualPropStatStore:
    """Reads manually prepared prop stats from JSON/JSONL runtime files."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or data_root() / 'settlement' / 'manual'
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths_for_sport(self, sport: str) -> List[Path]:
        return [
            self.root / f'{sport}_props_stats.json',
            self.root / f'{sport}_props_stats.jsonl',
            self.root / 'all_props_stats.json',
            self.root / 'all_props_stats.jsonl',
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
        if isinstance(payload, dict):
            rows = payload.get('rows')
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return []

    def lookup(self, bet: Dict) -> Optional[Dict]:
        for path in self._paths_for_sport(bet.get('sport', '')):
            for row in self._load_rows(path):
                if not self._row_matches_bet(row, bet):
                    continue
                stat_value = safe_float(row.get('stat_value'))
                if stat_value is None:
                    continue
                return {
                    'actual_value': stat_value,
                    'source': f'manual:{path.name}',
                    'notes': row.get('notes'),
                    'event_reference': row.get('event_reference') or row.get('event_id'),
                    'raw_status': row.get('status'),
                }
        return None

    def _row_matches_bet(self, row: Dict, bet: Dict) -> bool:
        if row.get('sport') and str(row.get('sport')).lower() != str(bet.get('sport')).lower():
            return False
        if _norm_market(row.get('market')) != _norm_market(bet.get('market')):
            return False
        if _norm_person(row.get('player_name')) != _norm_person(bet.get('player_name')):
            return False
        if row.get('event_id') and str(row.get('event_id')) == str(bet.get('event_id')):
            return True
        if _norm_team(row.get('home_team')) != _norm_team(bet.get('home_team')):
            return False
        if _norm_team(row.get('away_team')) != _norm_team(bet.get('away_team')):
            return False
        row_date = _coerce_dt(row.get('match_date'))
        bet_date = _coerce_dt(bet.get('match_date'))
        if row_date and bet_date and abs((row_date - bet_date).total_seconds()) > 36 * 3600:
            return False
        return True


class APISportsPropResolver:
    """Best-effort automatic settlement resolver using API-Sports."""

    def __init__(self, api_key: Optional[str] = None):
        client = APISportsClient(api_key=api_key)
        self.client = client if client.api_key else None

    def enabled(self) -> bool:
        return self.client is not None

    def lookup(self, bet: Dict) -> Optional[Dict]:
        if not self.client:
            return None
        sport = str(bet.get('sport') or '').lower()
        if sport == 'nba':
            return self._lookup_nba(bet)
        if sport == 'nfl':
            return self._lookup_nfl(bet)
        if sport == 'football':
            return self._lookup_football(bet)
        return None

    def _lookup_nba(self, bet: Dict) -> Optional[Dict]:
        target_dt = _coerce_dt(bet.get('match_date'))
        if not target_dt:
            return None
        season = str(target_dt.year if target_dt.month >= 9 else target_dt.year - 1)
        game = self._find_game(
            sport='nba',
            date=target_dt,
            params_builder=lambda d: {'date': d.date().isoformat(), 'league': 'standard', 'season': season},
            home_team=bet.get('home_team', ''),
            away_team=bet.get('away_team', ''),
        )
        if not game:
            return None
        game_id = _dig(game, 'id') or _dig(game, 'game', 'id')
        if not game_id:
            return None
        response = self.client.request('nba', '/players/statistics', {'game': game_id, 'season': season})
        rows = response.get('response', []) if isinstance(response, dict) else []
        player = self._find_player_row(rows, bet)
        if not player:
            return None
        stat_value = _extract_nba_value(player, bet.get('market'))
        if stat_value is None:
            return None
        return {
            'actual_value': stat_value,
            'source': 'api-sports:nba',
            'event_reference': str(game_id),
            'raw_status': _extract_status(game),
        }

    def _lookup_nfl(self, bet: Dict) -> Optional[Dict]:
        target_dt = _coerce_dt(bet.get('match_date'))
        if not target_dt:
            return None
        season = str(target_dt.year if target_dt.month >= 8 else target_dt.year - 1)
        game = self._find_game(
            sport='nfl',
            date=target_dt,
            params_builder=lambda d: {'date': d.date().isoformat(), 'league': '1', 'season': season},
            home_team=bet.get('home_team', ''),
            away_team=bet.get('away_team', ''),
        )
        if not game:
            return None
        game_id = _dig(game, 'id') or _dig(game, 'game', 'id')
        if not game_id:
            return None
        response = self.client.request('nfl', '/games/players', {'id': game_id})
        rows = response.get('response', []) if isinstance(response, dict) else []
        player = self._find_player_row(rows, bet)
        if not player:
            return None
        stat_value = _extract_nfl_value(player, bet.get('market'))
        if stat_value is None:
            return None
        return {
            'actual_value': stat_value,
            'source': 'api-sports:nfl',
            'event_reference': str(game_id),
            'raw_status': _extract_status(game),
        }

    def _lookup_football(self, bet: Dict) -> Optional[Dict]:
        target_dt = _coerce_dt(bet.get('match_date'))
        if not target_dt:
            return None
        fixture = self._find_game(
            sport='football',
            date=target_dt,
            params_builder=lambda d: {'date': d.date().isoformat()},
            home_team=bet.get('home_team', ''),
            away_team=bet.get('away_team', ''),
        )
        if not fixture:
            return None
        fixture_id = _dig(fixture, 'fixture', 'id') or _dig(fixture, 'id')
        if not fixture_id:
            return None
        response = self.client.request('football', '/fixtures/players', {'fixture': fixture_id})
        rows = response.get('response', []) if isinstance(response, dict) else []
        player = self._find_player_row(rows, bet)
        if not player:
            return None
        stat_value = _extract_football_value(player, bet.get('market'))
        if stat_value is None:
            return None
        return {
            'actual_value': stat_value,
            'source': 'api-sports:football',
            'event_reference': str(fixture_id),
            'raw_status': _extract_status(fixture),
        }

    def _find_game(self, *, sport: str, date: datetime, params_builder, home_team: str, away_team: str) -> Optional[Dict]:
        best: Optional[Tuple[int, Dict]] = None
        for day_offset in (0, -1, 1):
            current = date + timedelta(days=day_offset)
            payload = self.client.request(sport, '/games' if sport in {'nba', 'nfl'} else '/fixtures', params_builder(current))
            rows = payload.get('response', []) if isinstance(payload, dict) else []
            for row in rows:
                score = _team_match_score(row, home_team, away_team)
                if score is None:
                    continue
                if best is None or score < best[0]:
                    best = (score, row)
        if best and _game_is_final(best[1]):
            return best[1]
        return None

    def _find_player_row(self, rows: List[Dict], bet: Dict) -> Optional[Dict]:
        best: Optional[Tuple[int, Dict]] = None
        for row in rows:
            for candidate in _iter_player_rows(row):
                score = _player_match_score(candidate, bet.get('player_name', ''), bet.get('home_team', ''), bet.get('away_team', ''))
                if score is None:
                    continue
                if best is None or score < best[0]:
                    best = (score, candidate)
        return best[1] if best else None


class PropSettlementRunner:
    def __init__(
        self,
        tracker: Optional[UniversalBetTracker] = None,
        closing_manager: Optional[ClosingLineManager] = None,
        manual_store: Optional[ManualPropStatStore] = None,
        api_resolver: Optional[APISportsPropResolver] = None,
    ):
        self.tracker = tracker or UniversalBetTracker()
        self.closing = closing_manager or ClosingLineManager()
        self.manual_store = manual_store or ManualPropStatStore()
        self.api_resolver = api_resolver or APISportsPropResolver()
        self.unresolved_root = data_root() / 'settlement' / 'unresolved'
        self.unresolved_root.mkdir(parents=True, exist_ok=True)

    def settle_active_props(
        self,
        sport: Optional[str] = None,
        execution_mode: Optional[str] = None,
        settle_after_hours: float = 4.0,
        use_manual: bool = True,
        use_api: bool = True,
        max_bets: Optional[int] = None,
    ) -> Dict:
        active = self.tracker.get_active_bets(sport=sport, execution_mode=execution_mode)
        candidates = [b for b in active if _is_prop_bet(b)]
        if max_bets is not None:
            candidates = candidates[:max_bets]
        settled_records: List[PropSettlementRecord] = []
        unresolved: List[Dict] = []
        skipped_timing = 0
        for bet in candidates:
            if not _ready_for_settlement(bet, settle_after_hours=settle_after_hours):
                skipped_timing += 1
                continue
            resolved = None
            if use_manual:
                resolved = self.manual_store.lookup(bet)
            if not resolved and use_api and self.api_resolver.enabled():
                resolved = self.api_resolver.lookup(bet)
            if not resolved:
                unresolved.append({
                    'bet_id': bet.get('bet_id'),
                    'sport': bet.get('sport'),
                    'league': bet.get('league'),
                    'player_name': bet.get('player_name'),
                    'market': bet.get('market'),
                    'home_team': bet.get('home_team'),
                    'away_team': bet.get('away_team'),
                    'match_date': bet.get('match_date'),
                    'selection': bet.get('selection'),
                    'checked_at': now_iso(),
                })
                continue
            actual_value = safe_float(resolved.get('actual_value'))
            line = safe_float(bet.get('line'))
            if actual_value is None or line is None:
                unresolved.append({
                    'bet_id': bet.get('bet_id'),
                    'sport': bet.get('sport'),
                    'player_name': bet.get('player_name'),
                    'market': bet.get('market'),
                    'reason': 'missing_stat_or_line',
                    'checked_at': now_iso(),
                })
                continue
            result = settle_over_under(actual_value, line, bet.get('prop_side') or _infer_prop_side(bet.get('selection')))
            profit_loss = profit_from_decimal_odds(result, safe_float(bet.get('odds'), 0.0) or 0.0, safe_float(bet.get('kelly_stake'), 0.0) or 0.0)
            closing = self.closing.lookup_closing_odds(bet) or {}
            settlement_details = {
                'actual_stat_value': actual_value,
                'settlement_source': resolved.get('source'),
                'settlement_event_reference': resolved.get('event_reference'),
                'settlement_raw_status': resolved.get('raw_status'),
                'settlement_notes': resolved.get('notes'),
            }
            ok = self.tracker.settle_bet(
                bet['bet_id'],
                result,
                profit_loss,
                closing.get('closing_odds'),
                closing.get('closing_bookmaker'),
                settlement_details=settlement_details,
            )
            if ok:
                settled_records.append(PropSettlementRecord(
                    bet_id=str(bet.get('bet_id')),
                    sport=str(bet.get('sport')),
                    player_name=str(bet.get('player_name') or ''),
                    market=str(bet.get('market') or ''),
                    actual_value=float(actual_value),
                    line=float(line),
                    result=result,
                    profit_loss=float(profit_loss),
                    source=str(resolved.get('source') or ''),
                    event_reference=resolved.get('event_reference'),
                    raw_status=resolved.get('raw_status'),
                    notes=resolved.get('notes'),
                ))
        if unresolved:
            unresolved_path = self.unresolved_root / f"{sport or 'all'}_props_unresolved.jsonl"
            ensure_parent(unresolved_path)
            with unresolved_path.open('a', encoding='utf-8') as handle:
                for row in unresolved:
                    handle.write(json.dumps(row) + '\n')
        summary = {
            'timestamp': now_iso(),
            'sport': sport or 'all',
            'execution_mode': execution_mode or 'all',
            'active_prop_bets_seen': len(candidates),
            'settled_count': len(settled_records),
            'unresolved_count': len(unresolved),
            'skipped_timing_count': skipped_timing,
            'settled': [asdict(r) for r in settled_records[:25]],
        }
        return summary


def settle_over_under(actual_value: float, line: float, prop_side: str) -> str:
    actual = safe_float(actual_value)
    target = safe_float(line)
    if actual is None or target is None:
        return 'void'
    side = str(prop_side or '').strip().lower()
    if actual == target:
        return 'push'
    if side == 'over':
        return 'win' if actual > target else 'loss'
    if side == 'under':
        return 'win' if actual < target else 'loss'
    return 'void'


def profit_from_decimal_odds(result: str, odds: float, stake: float) -> float:
    odds = safe_float(odds, 0.0) or 0.0
    stake = safe_float(stake, 0.0) or 0.0
    if result == 'win':
        return round(stake * (odds - 1.0), 2)
    if result in ('push', 'void'):
        return 0.0
    return round(-stake, 2)


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description='Settle player props for NFL, NBA and football using manual stat files and optional API-Sports resolution.')
    parser.add_argument('--sport', choices=['football', 'nba', 'nfl', 'all'], default='all')
    parser.add_argument('--execution-mode', default=None)
    parser.add_argument('--settle-after-hours', type=float, default=4.0)
    parser.add_argument('--max-bets', type=int, default=None)
    parser.add_argument('--manual-only', action='store_true')
    parser.add_argument('--api-only', action='store_true')
    args = parser.parse_args(argv)

    runner = PropSettlementRunner()
    sport = None if args.sport == 'all' else args.sport
    summary = runner.settle_active_props(
        sport=sport,
        execution_mode=args.execution_mode,
        settle_after_hours=args.settle_after_hours,
        use_manual=not args.api_only,
        use_api=not args.manual_only,
        max_bets=args.max_bets,
    )
    print(json.dumps(summary, indent=2))
    return summary


# ------------------------- helper functions -------------------------

def _is_prop_bet(bet: Dict) -> bool:
    sport = str(bet.get('sport') or '').lower()
    market = _norm_market(bet.get('market'))
    return bool(bet.get('player_name')) and market in PROP_MARKETS_BY_SPORT.get(sport, set())


def _ready_for_settlement(bet: Dict, settle_after_hours: float = 4.0) -> bool:
    match_dt = _coerce_dt(bet.get('match_date'))
    if not match_dt:
        return False
    return datetime.now(timezone.utc) >= (match_dt + timedelta(hours=settle_after_hours))


def _coerce_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace('Z', '+00:00')
        try:
            dt = datetime.fromisoformat(text)
        except Exception:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                try:
                    dt = datetime.strptime(str(value), fmt)
                    break
                except Exception:
                    dt = None
            if dt is None:
                return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_text(value: str) -> str:
    return normalize_text(value)


def _norm_team(value: str) -> str:
    return normalize_team(value)


def _norm_person(value: str) -> str:
    return normalize_person(value)



def _norm_market(value: str) -> str:
    return str(value or '').strip().lower()


def _dig(data, *keys):
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int):
            if 0 <= key < len(current):
                current = current[key]
            else:
                return None
        else:
            return None
    return current


def _extract_status(row: Dict) -> Optional[str]:
    for candidate in (
        _dig(row, 'status', 'long'),
        _dig(row, 'status', 'short'),
        _dig(row, 'game', 'status', 'long'),
        _dig(row, 'game', 'status', 'short'),
        _dig(row, 'fixture', 'status', 'long'),
        _dig(row, 'fixture', 'status', 'short'),
    ):
        if candidate:
            return str(candidate)
    return None


def _game_is_final(row: Dict) -> bool:
    status = (_extract_status(row) or '').lower()
    if not status:
        # If status missing, still allow row to avoid blocking manual-like API responses.
        return True
    final_tokens = ('final', 'finished', 'after overtime', 'after penalties', 'ft', 'aet', 'pen', 'closed', 'ended')
    return any(token in status for token in final_tokens)


def _team_match_score(row: Dict, home_team: str, away_team: str) -> Optional[int]:
    row_home = _dig(row, 'teams', 'home', 'name') or _dig(row, 'teams', 'home') or _dig(row, 'home_team') or _dig(row, 'home', 'name') or ''
    row_away = _dig(row, 'teams', 'visitors', 'name') or _dig(row, 'teams', 'away', 'name') or _dig(row, 'teams', 'away') or _dig(row, 'away_team') or _dig(row, 'away', 'name') or ''
    score_home = team_match_score(row_home, home_team)
    score_away = team_match_score(row_away, away_team)
    if score_home is None or score_away is None:
        return None
    return score_home + score_away


def _iter_player_rows(row: Dict) -> Iterable[Dict]:
    if not isinstance(row, dict):
        return
    if _player_name_from_row(row):
        yield row
    for key, value in row.items():
        if isinstance(value, dict):
            yield from _iter_player_rows(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield from _iter_player_rows(item)


def _player_name_from_row(row: Dict) -> str:
    candidates = [
        _dig(row, 'player', 'name'),
        _dig(row, 'player', 'fullname'),
        _dig(row, 'player', 'full_name'),
        _dig(row, 'player', 'firstname'),
        row.get('player_name'),
        row.get('name'),
        row.get('player'),
        row.get('description'),
    ]
    firstname = _dig(row, 'player', 'firstname')
    lastname = _dig(row, 'player', 'lastname')
    if firstname or lastname:
        candidates.insert(0, f"{firstname or ''} {lastname or ''}".strip())
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def _player_match_score(row: Dict, player_name: str, home_team: str, away_team: str) -> Optional[int]:
    score = person_match_score(_player_name_from_row(row), player_name)
    if score is None:
        return None
    team_candidate = _dig(row, 'team', 'name') or _dig(row, 'statistics', 0, 'team', 'name') or row.get('team_name') or ''
    if team_candidate:
        if team_match_score(team_candidate, home_team) is None and team_match_score(team_candidate, away_team) is None:
            return None
    return score


def _extract_nba_value(row: Dict, market: str) -> Optional[float]:
    market = _norm_market(market)
    stats = row.get('statistics') if isinstance(row, dict) else None
    if isinstance(stats, list) and stats:
        stats = stats[0] if isinstance(stats[0], dict) else {}
    if not isinstance(stats, dict):
        stats = row
    if market == 'player_points':
        return _first_numeric(stats, 'points', 'pts')
    if market == 'player_rebounds':
        return _first_numeric(stats, 'totreb', 'rebounds', 'totalrebounds', 'total_rebounds')
    if market == 'player_assists':
        return _first_numeric(stats, 'assists', 'ast')
    if market == 'player_threes':
        return _first_numeric(stats, 'tpm', 'threepointsmade', 'three_pointers_made', 'threesmade', 'fg3m')
    return None


def _extract_nfl_value(row: Dict, market: str) -> Optional[float]:
    market = _norm_market(market)
    if market == 'player_pass_yds':
        return _first_numeric(row, 'passingyards', 'pass_yards', 'yards', 'yards_passing')
    if market == 'player_pass_tds':
        return _first_numeric(row, 'passingtouchdowns', 'pass_tds', 'touchdowns_passing', 'passingtds')
    if market == 'player_rush_yds':
        return _first_numeric(row, 'rushingyards', 'rush_yards', 'yards_rushing')
    if market == 'player_reception_yds':
        return _first_numeric(row, 'receivingyards', 'receiving_yards', 'yards_receiving')
    if market == 'player_receptions':
        return _first_numeric(row, 'receptions', 'catches')
    return None


def _extract_football_value(row: Dict, market: str) -> Optional[float]:
    market = _norm_market(market)
    stats = row.get('statistics')
    if isinstance(stats, list) and stats:
        stats = stats[0] if isinstance(stats[0], dict) else {}
    if not isinstance(stats, dict):
        stats = row
    if market == 'player_shots':
        return safe_float(_dig(stats, 'shots', 'total') or _dig(stats, 'shots', 'all'))
    if market == 'player_shots_on_target':
        return safe_float(_dig(stats, 'shots', 'on'))
    if market == 'player_assists_soccer':
        return safe_float(_dig(stats, 'goals', 'assists'))
    if market == 'player_passes':
        return safe_float(_dig(stats, 'passes', 'total'))
    if market == 'player_tackles':
        return safe_float(_dig(stats, 'tackles', 'total'))
    if market == 'player_cards':
        yellow = safe_float(_dig(stats, 'cards', 'yellow'), 0.0) or 0.0
        red = safe_float(_dig(stats, 'cards', 'red'), 0.0) or 0.0
        yellowred = safe_float(_dig(stats, 'cards', 'yellowred'), 0.0) or 0.0
        return yellow + red + yellowred
    return None


def _first_numeric(row: Dict, *keys: str) -> Optional[float]:
    flattened = {}
    _flatten_numeric(row, flattened)
    for key in keys:
        norm_key = _normalize_text(key).replace(' ', '')
        for candidate_key, value in flattened.items():
            if candidate_key.endswith(norm_key):
                return value
    return None


def _flatten_numeric(value, bucket: Dict[str, float], prefix: str = ''):
    if isinstance(value, dict):
        for key, inner in value.items():
            joined = f'{prefix}.{_normalize_text(key).replace(" ", "")}' if prefix else _normalize_text(key).replace(' ', '')
            _flatten_numeric(inner, bucket, joined)
    elif isinstance(value, list):
        for idx, inner in enumerate(value):
            _flatten_numeric(inner, bucket, f'{prefix}.{idx}' if prefix else str(idx))
    else:
        numeric = safe_float(value)
        if numeric is not None:
            bucket[prefix] = numeric


def _infer_prop_side(selection: Optional[str]) -> str:
    text = str(selection or '').lower()
    if ' under ' in f' {text} ':
        return 'under'
    return 'over'


if __name__ == '__main__':
    main()

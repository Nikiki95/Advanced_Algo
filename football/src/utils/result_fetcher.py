"""Fetch football results and settle tracked bets with domestic + UEFA fallback logic."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests

import sys
ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.api_sports_client import APISportsClient  # noqa: E402
from shared.closing_line import ClosingLineManager  # noqa: E402
from shared.player_name_matcher import normalize_team  # noqa: E402


class FootballDataFetcher:
    LEAGUE_CODES = {'D1': 'D1', 'D2': 'D2', 'E0': 'E0', 'SP1': 'SP1', 'I1': 'I1', 'F1': 'F1', 'P1': 'P1', 'N1': 'N1'}
    BASE_URL = 'https://www.football-data.co.uk/mmz4281/{season}/{league}.csv'
    UEFA_CODES = {'UCL', 'UEL', 'UECL', 'CHAMPIONS LEAGUE', 'EUROPA LEAGUE', 'CONFERENCE LEAGUE'}
    UEFA_NAME_HINTS = {
        'UCL': ('champions league',),
        'UEL': ('europa league',),
        'UECL': ('conference league', 'europa conference league'),
    }

    def __init__(self):
        self.cache_dir = Path('data/results_cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.api_client = APISportsClient()

    def _get_season_string(self, year: int | None = None) -> str:
        year = year or datetime.now().year
        return f"{str(year)[2:]}{str(year + 1)[2:]}"

    def fetch_results(self, league_code: str, season: str | None = None) -> pd.DataFrame:
        code = self.LEAGUE_CODES.get(league_code, league_code)
        season = season or self._get_season_string()
        cache = self.cache_dir / f'results_{code}_{season}.csv'
        if cache.exists():
            return self._prepare_results(pd.read_csv(cache))
        url = self.BASE_URL.format(season=season, league=code)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        cache.write_bytes(resp.content)
        return self._prepare_results(pd.read_csv(StringIO(resp.content.decode('latin-1'))))

    def _prepare_results(self, df: pd.DataFrame) -> pd.DataFrame:
        keep = [c for c in ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR'] if c in df.columns]
        df = df[keep].copy()
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        return df.dropna(subset=['FTHG', 'FTAG'])

    def match_result(self, home_team: str, away_team: str, match_date: str, league: str) -> Optional[Dict]:
        league_norm = str(league or '').upper().strip()
        if league_norm in self.UEFA_CODES or league_norm.startswith('UEFA'):
            return self._match_result_api(home_team, away_team, match_date, league_norm)

        league_map = {
            'D1': 'D1', 'D2': 'D2', 'E0': 'E0', 'SP1': 'SP1', 'I1': 'I1', 'F1': 'F1', 'P1': 'P1', 'N1': 'N1',
            'BUNDESLIGA': 'D1', '2. BUNDESLIGA': 'D2', 'PREMIER LEAGUE': 'E0', 'LA LIGA': 'SP1', 'SERIE A': 'I1',
            'LIGUE 1': 'F1', 'PRIMEIRA LIGA': 'P1', 'EREDIVISIE': 'N1',
        }
        code = league_map.get(league_norm, league if league in self.LEAGUE_CODES else 'D1')
        try:
            df = self.fetch_results(code)
        except Exception:
            df = pd.DataFrame()
        if not df.empty:
            home_norm = self._normalize_team_name(home_team)
            away_norm = self._normalize_team_name(away_team)
            for _, row in df.iterrows():
                row_home = self._normalize_team_name(str(row['HomeTeam']))
                row_away = self._normalize_team_name(str(row['AwayTeam']))
                if home_norm in row_home and away_norm in row_away:
                    return {
                        'home_goals': int(row['FTHG']),
                        'away_goals': int(row['FTAG']),
                        'result': row['FTR'],
                        'date': row.get('Date'),
                        'source': f'football-data:{code}',
                    }
        return self._match_result_api(home_team, away_team, match_date, league_norm)

    def _match_result_api(self, home_team: str, away_team: str, match_date: str, league: str) -> Optional[Dict]:
        if not self.api_client.api_key:
            return None
        target_dt = self._coerce_dt(match_date)
        if not target_dt:
            return None
        expected_keywords = self.UEFA_NAME_HINTS.get(league, ())
        best = None
        for day_offset in (0, -1, 1):
            day = (target_dt + timedelta(days=day_offset)).date().isoformat()
            payload = self.api_client.request('football', '/fixtures', {'date': day, 'timezone': 'UTC'})
            rows = payload.get('response', []) if isinstance(payload, dict) else []
            for row in rows:
                if not self._fixture_is_final(row):
                    continue
                score = self._fixture_match_score(row, home_team, away_team)
                if score is None:
                    continue
                league_name = str(row.get('league', {}).get('name') or '').lower()
                if expected_keywords and not any(k in league_name for k in expected_keywords):
                    continue
                if best is None or score < best[0]:
                    best = (score, row)
        if not best:
            return None
        row = best[1]
        home_goals = int(row.get('goals', {}).get('home') or 0)
        away_goals = int(row.get('goals', {}).get('away') or 0)
        result = 'H' if home_goals > away_goals else 'A' if away_goals > home_goals else 'D'
        return {
            'home_goals': home_goals,
            'away_goals': away_goals,
            'result': result,
            'date': row.get('fixture', {}).get('date'),
            'source': f"api-sports:{row.get('league', {}).get('name', 'football')}",
            'event_reference': str(row.get('fixture', {}).get('id') or ''),
        }

    def _fixture_match_score(self, row: Dict, home_team: str, away_team: str) -> Optional[int]:
        row_home = row.get('teams', {}).get('home', {}).get('name') or ''
        row_away = row.get('teams', {}).get('away', {}).get('name') or ''
        home_norm = normalize_team(home_team)
        away_norm = normalize_team(away_team)
        row_home_norm = normalize_team(row_home)
        row_away_norm = normalize_team(row_away)
        if home_norm not in row_home_norm and row_home_norm not in home_norm:
            return None
        if away_norm not in row_away_norm and row_away_norm not in away_norm:
            return None
        return abs(len(home_norm) - len(row_home_norm)) + abs(len(away_norm) - len(row_away_norm))

    def _fixture_is_final(self, row: Dict) -> bool:
        status = str(row.get('fixture', {}).get('status', {}).get('short') or row.get('fixture', {}).get('status', {}).get('long') or '').upper()
        if not status:
            return False
        final_tokens = {'FT', 'AET', 'PEN'}
        return status in final_tokens or 'FINISHED' in status or 'MATCH FINISHED' in status

    def _coerce_dt(self, value: str | datetime | None) -> Optional[datetime]:
        if value is None:
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

    def _normalize_team_name(self, name: str) -> str:
        name = normalize_team(name)
        name = re.sub(r'\s+', ' ', name)
        return name.strip()


class ResultSettler:
    def __init__(self, tracker, fetcher):
        self.tracker = tracker
        self.fetcher = fetcher
        self.closing_lines = ClosingLineManager()

    def settle_all_matches(self, leagues: Optional[list[str]] = None):
        active_bets = self.tracker.get_active_bets(sport='football') if hasattr(self.tracker, 'get_active_bets') else self.tracker.get_active_bets()
        if leagues:
            wanted = {str(l).upper() for l in leagues}
            active_bets = [b for b in active_bets if str(b.get('league', '')).upper() in wanted]
        settled = 0
        for bet in active_bets:
            match_date = bet.get('match_date', '')
            if not match_date:
                continue
            try:
                match_dt = datetime.fromisoformat(str(match_date).replace('Z', '+00:00')).replace(tzinfo=None)
                if datetime.utcnow() - match_dt < timedelta(hours=2):
                    continue
            except Exception:
                continue
            result = self.fetcher.match_result(bet.get('home_team', ''), bet.get('away_team', ''), match_date, bet.get('league', ''))
            if not result:
                continue
            outcome = self._calculate_outcome(bet, result)
            pnl = self._calculate_pnl(bet, outcome)
            closing = self.closing_lines.lookup_closing_odds(bet) or {}
            settlement_details = {
                'settlement_source': result.get('source'),
                'settlement_event_reference': result.get('event_reference'),
                'home_score': result.get('home_goals'),
                'away_score': result.get('away_goals'),
            }
            if self.tracker.settle_bet(bet['bet_id'], outcome, pnl, closing.get('closing_odds'), closing.get('closing_bookmaker'), settlement_details=settlement_details):
                settled += 1
        print(f"[Settler] {settled} bets settled")

    def _calculate_outcome(self, bet: Dict, result: Dict) -> str:
        market = bet.get('market') or bet.get('bet_type', '')
        selection = str(bet.get('selection', ''))
        home_goals, away_goals = int(result['home_goals']), int(result['away_goals'])
        actual_result = result['result']

        if market in ('1x2', '1', 'X', '2') or bet.get('bet_type') in ('1', 'X', '2'):
            bet_type = bet.get('bet_type', market)
            mapping = {'1': 'H', 'X': 'D', '2': 'A'}
            return 'win' if mapping.get(bet_type) == actual_result else 'loss'

        if market in ('dc', '1X', 'X2', '12') or bet.get('bet_type') in ('1X', 'X2', '12'):
            bet_type = bet.get('bet_type', market)
            if bet_type == '1X':
                return 'win' if actual_result in ('H', 'D') else 'loss'
            if bet_type == 'X2':
                return 'win' if actual_result in ('D', 'A') else 'loss'
            if bet_type == '12':
                return 'win' if actual_result in ('H', 'A') else 'loss'

        if str(market).lower() in ('ou', 'totals') or selection.lower().startswith('over') or selection.lower().startswith('under'):
            line = bet.get('line')
            if line is None:
                match = re.search(r'([0-9]+(?:\.[0-9]+)?)', selection or bet.get('bet_type', ''))
                line = float(match.group(1)) if match else 2.5
            total_goals = home_goals + away_goals
            if selection.lower().startswith('over'):
                if total_goals > float(line):
                    return 'win'
                if total_goals == float(line):
                    return 'push'
                return 'loss'
            if selection.lower().startswith('under'):
                if total_goals < float(line):
                    return 'win'
                if total_goals == float(line):
                    return 'push'
                return 'loss'

        return 'loss'

    def _calculate_pnl(self, bet: Dict, outcome: str) -> float:
        stake = float(bet.get('kelly_stake') or 0)
        odds = float(bet.get('odds') or 0)
        if outcome == 'win':
            return round(stake * (odds - 1), 2)
        if outcome in ('void', 'push'):
            return 0.0
        return round(-stake, 2)


fetcher = FootballDataFetcher()
settler_class = ResultSettler

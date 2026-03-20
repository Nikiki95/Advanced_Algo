"""NBA odds scraper with bookmaker option tracking for line shopping."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.line_shopping import best_from_options  # noqa: E402
from shared.runtime_utils import load_env  # noqa: E402

load_env()

try:
    from nba.config import THEODDS_API_KEY, THEODDS_BASE_URL, NBA_SPORT_KEY, REGIONS, ODDS_MARKETS, ODDS_FORMAT
except Exception:
    THEODDS_API_KEY = os.getenv('THEODDS_API_KEY', '')
    THEODDS_BASE_URL = 'https://api.the-odds-api.com/v4'
    NBA_SPORT_KEY = 'basketball_nba'
    REGIONS = 'eu'
    ODDS_MARKETS = ['h2h', 'spreads', 'totals']
    ODDS_FORMAT = 'decimal'


class NBAOddsScraper:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or THEODDS_API_KEY
        self.base_url = THEODDS_BASE_URL

    def _normalize_team(self, name: str) -> str:
        """Map full team names to model short names."""
        mapping = {
            'Los Angeles Lakers': 'LAL',
            'Golden State Warriors': 'Golden State',
            'LA Clippers': 'LA Clippers',
            'Atlanta Hawks': 'Atlanta',
            'Boston Celtics': 'Boston',
            'Brooklyn Nets': 'Brooklyn',
            'Charlotte Hornets': 'Charlotte',
            'Chicago Bulls': 'Chicago',
            'Cleveland Cavaliers': 'Cleveland',
            'Dallas Mavericks': 'Dallas',
            'Denver Nuggets': 'Denver',
            'Detroit Pistons': 'Detroit',
            'Houston Rockets': 'Houston',
            'Indiana Pacers': 'Indiana',
            'Memphis Grizzlies': 'Memphis',
            'Miami Heat': 'Miami',
            'Milwaukee Bucks': 'Milwaukee',
            'Minnesota Timberwolves': 'Minnesota',
            'New Orleans Pelicans': 'New Orleans',
            'New York Knicks': 'New York',
            'Oklahoma City Thunder': 'Oklahoma City',
            'Orlando Magic': 'Orlando',
            'Philadelphia 76ers': 'Philadelphia',
            'Phoenix Suns': 'Phoenix',
            'Portland Trail Blazers': 'Portland',
            'Sacramento Kings': 'Sacramento',
            'San Antonio Spurs': 'San Antonio',
            'Toronto Raptors': 'Toronto',
            'Utah Jazz': 'Utah',
            'Washington Wizards': 'Washington',
        }
        return mapping.get(name, name)

    def fetch_upcoming(self, days: int = 1) -> pd.DataFrame:
        if not self.api_key:
            logger.warning('No API key — returning empty DataFrame')
            return pd.DataFrame()
        url = f"{self.base_url}/sports/{NBA_SPORT_KEY}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': REGIONS,
            'markets': ','.join(ODDS_MARKETS),
            'oddsFormat': ODDS_FORMAT,
            'dateFormat': 'iso',
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return self._parse_odds(resp.json())
        except Exception as e:
            logger.error(f'Error fetching NBA odds: {e}')
            return pd.DataFrame()

    def _parse_odds(self, data: List[Dict]) -> pd.DataFrame:
        games = []
        for game in data:
            home_raw = game.get('home_team')
            away_raw = game.get('away_team')
            info = {
                'game_id': game.get('id'),
                'home_team': self._normalize_team(home_raw),
                'away_team': self._normalize_team(away_raw),
                'commence_time': game.get('commence_time'),
                'sport_key': game.get('sport_key'),
            }
            home_ml_opts, away_ml_opts = [], []
            home_spread_opts, away_spread_opts = [], []
            over_opts, under_opts = [], []
            home_spread_line = None
            total_line = None
            for bookmaker in game.get('bookmakers', []):
                bm = bookmaker.get('key', 'unknown')
                markets = {m['key']: m for m in bookmaker.get('markets', [])}
                if 'h2h' in markets:
                    for outcome in markets['h2h'].get('outcomes', []):
                        if outcome['name'] == home_raw:
                            home_ml_opts.append({'bookmaker': bm, 'odds': outcome['price']})
                        elif outcome['name'] == away_raw:
                            away_ml_opts.append({'bookmaker': bm, 'odds': outcome['price']})
                if 'spreads' in markets:
                    for outcome in markets['spreads'].get('outcomes', []):
                        row = {'bookmaker': bm, 'odds': outcome['price'], 'line': outcome.get('point')}
                        if outcome['name'] == home_raw:
                            home_spread_opts.append(row)
                            home_spread_line = outcome.get('point', home_spread_line)
                        elif outcome['name'] == away_raw:
                            away_spread_opts.append(row)
                if 'totals' in markets:
                    for outcome in markets['totals'].get('outcomes', []):
                        row = {'bookmaker': bm, 'odds': outcome['price'], 'line': outcome.get('point')}
                        total_line = outcome.get('point', total_line)
                        if outcome['name'] == 'Over':
                            over_opts.append(row)
                        elif outcome['name'] == 'Under':
                            under_opts.append(row)
            best_home_bk, best_home_odds, home_ml_opts = best_from_options(home_ml_opts)
            best_away_bk, best_away_odds, away_ml_opts = best_from_options(away_ml_opts)
            best_hs_bk, best_hs_odds, home_spread_opts = best_from_options(home_spread_opts)
            best_as_bk, best_as_odds, away_spread_opts = best_from_options(away_spread_opts)
            best_over_bk, best_over_odds, over_opts = best_from_options(over_opts)
            best_under_bk, best_under_odds, under_opts = best_from_options(under_opts)
            info.update({
                'home_odds': best_home_odds, 'away_odds': best_away_odds,
                'home_odds_bk': best_home_bk, 'away_odds_bk': best_away_bk,
                'home_odds_options': home_ml_opts, 'away_odds_options': away_ml_opts,
                'home_spread': home_spread_line, 'home_spread_odds': best_hs_odds,
                'away_spread_odds': best_as_odds,
                'home_spread_bk': best_hs_bk, 'away_spread_bk': best_as_bk,
                'home_spread_options': home_spread_opts, 'away_spread_options': away_spread_opts,
                'over_line': total_line, 'over_odds': best_over_odds, 'under_odds': best_under_odds,
                'over_bk': best_over_bk, 'under_bk': best_under_bk,
                'over_odds_options': over_opts, 'under_odds_options': under_opts,
            })
            games.append(info)
        df = pd.DataFrame(games)
        logger.info(f'{len(df)} NBA games loaded')
        return df


scraper = NBAOddsScraper()

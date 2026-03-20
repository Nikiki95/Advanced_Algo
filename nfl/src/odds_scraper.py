"""NFL odds scraper with bookmaker option tracking for line shopping."""
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
    from nfl.config import THEODDS_API_KEY, THEODDS_BASE_URL, NFL_SPORT_KEY, REGIONS
except Exception:
    THEODDS_API_KEY = os.getenv('THEODDS_API_KEY', '')
    THEODDS_BASE_URL = 'https://api.the-odds-api.com/v4'
    NFL_SPORT_KEY = 'americanfootball_nfl'
    REGIONS = 'us'

TEAM_NAME_MAP = {
    'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL', 'Buffalo Bills': 'BUF',
    'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI', 'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE',
    'Dallas Cowboys': 'DAL', 'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX', 'Kansas City Chiefs': 'KC',
    'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC', 'Los Angeles Rams': 'LAR', 'Miami Dolphins': 'MIA',
    'Minnesota Vikings': 'MIN', 'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT', 'San Francisco 49ers': 'SF',
    'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB', 'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS',
}


class NFLOddsScraper:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or THEODDS_API_KEY
        self.base_url = THEODDS_BASE_URL

    def _normalize(self, name: str) -> str:
        return TEAM_NAME_MAP.get(name, name)

    def fetch_upcoming(self) -> pd.DataFrame:
        if not self.api_key:
            logger.warning('No API key — returning empty DataFrame')
            return pd.DataFrame()
        url = f"{self.base_url}/sports/{NFL_SPORT_KEY}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': REGIONS,
            'markets': 'h2h,spreads,totals',
            'oddsFormat': 'decimal',
            'dateFormat': 'iso',
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return self._parse(resp.json())
        except Exception as e:
            logger.error(f'NFL odds fetch error: {e}')
            return pd.DataFrame()

    def _parse(self, data: List[Dict]) -> pd.DataFrame:
        games = []
        for game in data:
            home_raw = game.get('home_team', '')
            away_raw = game.get('away_team', '')
            info = {
                'game_id': game.get('id'),
                'home_team': self._normalize(home_raw),
                'away_team': self._normalize(away_raw),
                'commence_time': game.get('commence_time'),
            }
            home_ml_opts, away_ml_opts = [], []
            home_spread_opts, away_spread_opts = [], []
            over_opts, under_opts = [], []
            spread_line = None
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
                            spread_line = outcome.get('point', spread_line)
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
                'spread': spread_line, 'home_spread_odds': best_hs_odds, 'away_spread_odds': best_as_odds,
                'home_spread_bk': best_hs_bk, 'away_spread_bk': best_as_bk,
                'home_spread_options': home_spread_opts, 'away_spread_options': away_spread_opts,
                'total_line': total_line, 'over_odds': best_over_odds, 'under_odds': best_under_odds,
                'over_bk': best_over_bk, 'under_bk': best_under_bk,
                'over_odds_options': over_opts, 'under_odds_options': under_opts,
            })
            games.append(info)
        df = pd.DataFrame(games)
        logger.info(f'{len(df)} NFL games loaded')
        return df


scraper = NFLOddsScraper()

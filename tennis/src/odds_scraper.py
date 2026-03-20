"""Tournament-based tennis odds scraper."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.line_shopping import best_from_options
from shared.runtime_utils import load_env

load_env()

try:
    from tennis.config import THEODDS_API_KEY, THEODDS_BASE_URL, REGIONS
except Exception:
    THEODDS_API_KEY = os.getenv('THEODDS_API_KEY', '')
    THEODDS_BASE_URL = 'https://api.the-odds-api.com/v4'
    REGIONS = 'eu'


class TennisOddsScraper:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or THEODDS_API_KEY
        self.base_url = THEODDS_BASE_URL

    def fetch_tournament(self, tournament_key: str) -> pd.DataFrame:
        if not self.api_key:
            return pd.DataFrame()
        url = f"{self.base_url}/sports/{tournament_key}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': REGIONS,
            'markets': 'h2h',
            'oddsFormat': 'decimal',
            'dateFormat': 'iso',
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return self._parse(resp.json(), tournament_key)
        except Exception:
            return pd.DataFrame()

    def _parse(self, data: List[Dict], tournament_key: str) -> pd.DataFrame:
        matches = []
        for match in data:
            home = match.get('home_team', '')
            away = match.get('away_team', '')
            home_opts, away_opts = [], []
            for bookmaker in match.get('bookmakers', []):
                bm = bookmaker.get('key', 'unknown')
                for market in bookmaker.get('markets', []):
                    if market.get('key') != 'h2h':
                        continue
                    for outcome in market.get('outcomes', []):
                        row = {'bookmaker': bm, 'odds': outcome.get('price')}
                        if outcome.get('name') == home:
                            home_opts.append(row)
                        elif outcome.get('name') == away:
                            away_opts.append(row)
            best_home_bk, best_home_odds, home_opts = best_from_options(home_opts)
            best_away_bk, best_away_odds, away_opts = best_from_options(away_opts)
            matches.append({
                'match_id': match.get('id'),
                'tournament_key': tournament_key,
                'home_player': home,
                'away_player': away,
                'commence_time': match.get('commence_time'),
                'home_odds': best_home_odds,
                'away_odds': best_away_odds,
                'home_odds_bk': best_home_bk,
                'away_odds_bk': best_away_bk,
                'home_odds_options': home_opts,
                'away_odds_options': away_opts,
            })
        return pd.DataFrame(matches)

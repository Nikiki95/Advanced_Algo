"""Thin The Odds API helpers for event-level player props."""
from __future__ import annotations

import requests
from typing import Dict, List, Optional

from .runtime_utils import load_env

load_env()


class TheOddsPropAPI:
    def __init__(self, api_key: str, base_url: str = 'https://api.the-odds-api.com/v4'):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

    def fetch_event_index(self, sport_key: str, regions: str = 'eu') -> List[Dict]:
        if not self.api_key:
            return []
        url = f"{self.base_url}/sports/{sport_key}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': regions,
            'markets': 'h2h',
            'oddsFormat': 'decimal',
            'dateFormat': 'iso',
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def fetch_event_props(self, sport_key: str, event_id: str, markets: List[str], regions: str = 'eu') -> Optional[Dict]:
        if not self.api_key or not markets:
            return None
        url = f"{self.base_url}/sports/{sport_key}/events/{event_id}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': regions,
            'markets': ','.join(markets),
            'oddsFormat': 'decimal',
            'dateFormat': 'iso',
        }
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code >= 400:
            return None
        return resp.json()

    @staticmethod
    def parse_over_under_rows(event_payload: Optional[Dict]) -> List[Dict]:
        if not isinstance(event_payload, dict):
            return []
        rows = []
        for bookmaker in event_payload.get('bookmakers', []):
            bm_key = bookmaker.get('key', 'unknown')
            for market in bookmaker.get('markets', []):
                market_key = market.get('key', '')
                for outcome in market.get('outcomes', []):
                    name = outcome.get('name')
                    description = outcome.get('description')
                    point = outcome.get('point')
                    price = outcome.get('price')
                    if name not in ('Over', 'Under'):
                        continue
                    if description in (None, '') or point in (None, '') or price in (None, ''):
                        continue
                    rows.append({
                        'event_id': event_payload.get('id'),
                        'sport_key': event_payload.get('sport_key'),
                        'home_team': event_payload.get('home_team'),
                        'away_team': event_payload.get('away_team'),
                        'commence_time': event_payload.get('commence_time'),
                        'bookmaker': bm_key,
                        'market': market_key,
                        'player_name': description,
                        'side': str(name).lower(),
                        'line': point,
                        'odds': price,
                    })
        return rows

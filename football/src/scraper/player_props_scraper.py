"""Football player props scraper for domestic leagues and UEFA competitions."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.prop_api import TheOddsPropAPI
from football.config import PLAYER_PROP_MARKETS, UEFA_COMPETITIONS
from scraper.theoddsapi import TheOddsAPIClient


SCOPE_TO_SPORT_KEY = {
    'D1': 'soccer_germany_bundesliga',
    'D2': 'soccer_germany_bundesliga_2',
    'E0': 'soccer_epl',
    'SP1': 'soccer_spain_la_liga',
    'I1': 'soccer_italy_serie_a',
    'F1': 'soccer_france_ligue_one',
    'P1': 'soccer_portugal_primeira_liga',
    'N1': 'soccer_netherlands_eredivisie',
    'UCL': 'soccer_uefa_champs_league',
    'UEL': 'soccer_uefa_europa_league',
    'UECL': 'soccer_uefa_europa_conference_league',
}


class FootballPlayerPropsScraper:
    def __init__(self, api_key: Optional[str] = None):
        self.game_client = TheOddsAPIClient(api_key=api_key)
        self.api = TheOddsPropAPI(self.game_client.api_key, base_url=self.game_client.BASE_URL)

    def fetch_scope_props(self, scopes: List[str], markets: Optional[List[str]] = None, max_events_per_scope: Optional[int] = None) -> List[Dict]:
        markets = markets or list(PLAYER_PROP_MARKETS)
        events = []
        for scope in scopes:
            sport_key = SCOPE_TO_SPORT_KEY.get(scope)
            if not sport_key:
                continue
            matches = self.game_client.get_live_odds(sport_key)
            for idx, match in enumerate(matches):
                if max_events_per_scope is not None and idx >= max_events_per_scope:
                    break
                payload = self.api.fetch_event_props(sport_key, match.event_id, markets, regions='eu')
                rows = self.api.parse_over_under_rows(payload)
                events.append({
                    'event_id': match.event_id,
                    'league': scope,
                    'home_team': match.home_team,
                    'away_team': match.away_team,
                    'match_date': match.commence_time.isoformat(),
                    'rows': rows,
                })
        return events

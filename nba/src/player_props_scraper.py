"""NBA player props scraper using The Odds API event-level markets."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.prop_api import TheOddsPropAPI
from nba.config import THEODDS_API_KEY, THEODDS_BASE_URL, NBA_SPORT_KEY, REGIONS, PLAYER_PROP_MARKETS
from odds_scraper import NBAOddsScraper


class NBAPlayerPropsScraper:
    def __init__(self, api_key: Optional[str] = None):
        self.api = TheOddsPropAPI(api_key or THEODDS_API_KEY, base_url=THEODDS_BASE_URL)
        self.game_scraper = NBAOddsScraper(api_key=api_key or THEODDS_API_KEY)

    def fetch_upcoming_props(self, markets: Optional[List[str]] = None, max_games: Optional[int] = None) -> List[Dict]:
        markets = markets or list(PLAYER_PROP_MARKETS)
        games = self.game_scraper.fetch_upcoming(days=1)
        events = []
        for idx, (_, game) in enumerate(games.iterrows()):
            if max_games is not None and idx >= max_games:
                break
            game = game.to_dict()
            payload = self.api.fetch_event_props(NBA_SPORT_KEY, game['game_id'], markets, regions=REGIONS)
            rows = self.api.parse_over_under_rows(payload)
            events.append({
                'event_id': game['game_id'],
                'league': 'NBA',
                'home_team': game['home_team'],
                'away_team': game['away_team'],
                'match_date': game.get('commence_time'),
                'rows': rows,
            })
        return events

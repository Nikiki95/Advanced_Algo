"""
TheOddsAPI Integration v2
- Fetches 1X2 + Over/Under in one API call
- Best-odds extraction across all bookmakers
- Rate limit tracking
"""
import os
import json
from typing import List, Dict, Optional
from datetime import datetime
import requests
from dataclasses import dataclass, field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))

try:
    from config import football_config as cfg
    DEFAULT_API_KEY = cfg.THEODDS_API_KEY
except ImportError:
    DEFAULT_API_KEY = os.getenv("THEODDS_API_KEY", "")


@dataclass
class TheOddsAPIMatch:
    """Match data from TheOddsAPI with all markets."""
    event_id: str
    home_team: str
    away_team: str
    commence_time: datetime

    # 1X2
    odds_1: Dict[str, float] = field(default_factory=dict)
    odds_x: Dict[str, float] = field(default_factory=dict)
    odds_2: Dict[str, float] = field(default_factory=dict)

    # Implied probabilities
    implied_prob_1: float = 0.0
    implied_prob_x: float = 0.0
    implied_prob_2: float = 0.0

    # Over/Under (NEW)
    ou_line: float = 2.5
    odds_over: Dict[str, float] = field(default_factory=dict)
    odds_under: Dict[str, float] = field(default_factory=dict)

    # Double Chance (derived or direct)
    odds_dc_1x: Dict[str, float] = field(default_factory=dict)
    odds_dc_x2: Dict[str, float] = field(default_factory=dict)
    odds_dc_12: Dict[str, float] = field(default_factory=dict)

    @property
    def best_odds_1(self) -> float:
        return max(self.odds_1.values()) if self.odds_1 else 0

    @property
    def best_odds_x(self) -> float:
        return max(self.odds_x.values()) if self.odds_x else 0

    @property
    def best_odds_2(self) -> float:
        return max(self.odds_2.values()) if self.odds_2 else 0

    @property
    def best_odds_over(self) -> float:
        return max(self.odds_over.values()) if self.odds_over else 0

    @property
    def best_odds_under(self) -> float:
        return max(self.odds_under.values()) if self.odds_under else 0


class TheOddsAPIClient:
    """
    Client for TheOddsAPI (free tier: 500 calls/month).
    v2: Fetches h2h + totals in one call to save API quota.
    """

    BASE_URL = "https://api.the-odds-api.com/v4"

    SPORTS = {
        "soccer_germany_bundesliga": "Bundesliga",
        "soccer_germany_2_bundesliga": "2. Bundesliga",
        "soccer_epl": "Premier League",
        "soccer_spain_la_liga": "La Liga",
        "soccer_italy_serie_a": "Serie A",
        "soccer_france_ligue_one": "Ligue 1",
        "soccer_portugal_primeira_liga": "Primeira Liga",
        "soccer_netherlands_eredivisie": "Eredivisie",
        "soccer_uefa_champs_league": "Champions League",
        "soccer_uefa_europa_league": "Europa League",
        "soccer_uefa_europa_conference_league": "Conference League",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or DEFAULT_API_KEY
        if not self.api_key:
            raise ValueError(
                "THEODDS_API_KEY not set. Get a free key at https://the-odds-api.com/")
        self.remaining_calls = None

    def get_remaining_calls(self) -> int:
        url = f"{self.BASE_URL}/sports"
        resp = requests.get(url, params={"apiKey": self.api_key}, timeout=30)
        self.remaining_calls = int(resp.headers.get('x-requests-remaining', 0))
        used = resp.headers.get('x-requests-used', '?')
        print(f"[TheOddsAPI] Remaining: {self.remaining_calls} | Used: {used}")
        return self.remaining_calls

    def get_live_odds(self, sport: str = "soccer_germany_bundesliga",
                      markets: str = "h2h,totals",
                      regions: str = "eu") -> List[TheOddsAPIMatch]:
        """
        Fetches 1X2 + Over/Under in a single API call.
        """
        url = f"{self.BASE_URL}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }

        print(f"[TheOddsAPI] Fetching {sport} ({markets})...")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        self.remaining_calls = int(response.headers.get('x-requests-remaining', 0))
        print(f"[TheOddsAPI] Remaining calls: {self.remaining_calls}")

        data = response.json()
        return self._parse_matches(data)

    def _parse_matches(self, data: List[Dict]) -> List[TheOddsAPIMatch]:
        matches = []
        for event in data:
            try:
                ct = event.get("commence_time", "")
                if ct:
                    ct = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                else:
                    ct = datetime.now()
            except Exception:
                ct = datetime.now()

            match = TheOddsAPIMatch(
                event_id=event.get("id", ""),
                home_team=event.get("home_team", ""),
                away_team=event.get("away_team", ""),
                commence_time=ct,
            )

            home = event.get("home_team", "")
            away = event.get("away_team", "")

            for bookmaker in event.get("bookmakers", []):
                bk_name = bookmaker.get("key", "unknown")
                mkts = {m["key"]: m for m in bookmaker.get("markets", [])}

                # H2H (1X2)
                if "h2h" in mkts:
                    outcomes = {
                        o["name"]: o["price"]
                        for o in mkts["h2h"].get("outcomes", [])
                    }
                    if home in outcomes:
                        match.odds_1[bk_name] = outcomes[home]
                    if away in outcomes:
                        match.odds_2[bk_name] = outcomes[away]
                    if "Draw" in outcomes:
                        match.odds_x[bk_name] = outcomes["Draw"]

                # Totals (Over/Under)
                if "totals" in mkts:
                    for outcome in mkts["totals"].get("outcomes", []):
                        line = outcome.get("point", 2.5)
                        match.ou_line = line
                        if outcome["name"] == "Over":
                            match.odds_over[bk_name] = outcome["price"]
                        elif outcome["name"] == "Under":
                            match.odds_under[bk_name] = outcome["price"]

            # Implied probabilities
            if match.best_odds_1 > 0:
                match.implied_prob_1 = 1.0 / match.best_odds_1
            if match.best_odds_x > 0:
                match.implied_prob_x = 1.0 / match.best_odds_x
            if match.best_odds_2 > 0:
                match.implied_prob_2 = 1.0 / match.best_odds_2

            matches.append(match)

        print(f"[TheOddsAPI] Parsed {len(matches)} matches")
        return matches


if __name__ == "__main__":
    try:
        client = TheOddsAPIClient()
        client.get_remaining_calls()
        matches = client.get_live_odds("soccer_germany_bundesliga")
        for m in matches[:3]:
            print(f"\n{m.home_team} vs {m.away_team}")
            print(f"  1X2: {m.best_odds_1:.2f} / {m.best_odds_x:.2f} / {m.best_odds_2:.2f}")
            print(f"  O/U {m.ou_line}: {m.best_odds_over:.2f} / {m.best_odds_under:.2f}")
    except Exception as e:
        print(f"Error: {e}")

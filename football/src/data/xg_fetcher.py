"""
xG Data Fetcher v1
Fetches Expected Goals data from multiple sources:
1. football-data.co.uk (has xG columns in newer CSVs)
2. FBref / StatsBomb (free xG data via HTML scraping)
3. Understat (JSON API, no key needed)

Used to train Dixon-Coles on xG instead of actual goals.
"""

import pandas as pd
import numpy as np
import requests
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from io import StringIO
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XGDataFetcher:
    """
    Fetches xG data from free sources.

    Priority:
    1. football-data.co.uk (if xG columns available)
    2. Understat (JSON, no key needed, 6 leagues)
    3. Fallback: actual goals (FTHG/FTAG)
    """

    # football-data.co.uk
    FD_BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"

    # Understat league mapping
    UNDERSTAT_LEAGUES = {
        'D1': 'Bundesliga',
        'E0': 'EPL',
        'SP1': 'La_Liga',
        'I1': 'Serie_A',
        'F1': 'Ligue_1',
        # No 2nd divisions, Portuguese, Dutch leagues on Understat
    }

    # FBref league URLs
    FBREF_LEAGUE_IDS = {
        'D1': '20',    # Bundesliga
        'E0': '9',     # Premier League
        'SP1': '12',   # La Liga
        'I1': '11',    # Serie A
        'F1': '13',    # Ligue 1
        'P1': '32',    # Primeira Liga
        'N1': '23',    # Eredivisie
    }

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("data/xg_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_training_data(self, league_code: str,
                            seasons: int = 3,
                            prefer_xg: bool = True) -> pd.DataFrame:
        """
        Fetches training data, preferring xG when available.

        Returns DataFrame with columns:
            Date, HomeTeam, AwayTeam, FTHG, FTAG, xHG, xAG, FTR
            (xHG/xAG = expected goals, falls back to FTHG/FTAG)
        """
        all_data = []

        current_year = datetime.now().year
        current_month = datetime.now().month

        for i in range(seasons):
            # Season logic: if month >= 7, current season started this year
            if current_month >= 7:
                start_year = current_year - i
            else:
                start_year = current_year - 1 - i

            season_str = f"{str(start_year)[2:]}{str(start_year + 1)[2:]}"
            logger.info(f"Fetching {league_code} season {start_year}/{start_year+1}...")

            df = self._fetch_season(league_code, season_str, prefer_xg)
            if df is not None and len(df) > 0:
                df['season'] = f"{start_year}/{start_year+1}"
                all_data.append(df)

        if not all_data:
            logger.warning(f"No data found for {league_code}")
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values('Date').reset_index(drop=True)

        xg_count = combined['xg_source'].value_counts().to_dict() if 'xg_source' in combined.columns else {}
        logger.info(f"Total: {len(combined)} matches. xG sources: {xg_count}")

        return combined

    def _fetch_season(self, league: str, season: str,
                      prefer_xg: bool) -> Optional[pd.DataFrame]:
        """Fetch one season of data."""
        # Try football-data.co.uk first (always has results, sometimes xG)
        df = self._fetch_football_data(league, season)
        if df is None or df.empty:
            return None

        if prefer_xg:
            # Check if football-data already has xG
            if 'AvgxHG' in df.columns or 'xHG' in df.columns:
                df = self._extract_fd_xg(df)
                logger.info(f"  Using football-data.co.uk xG")
                return df

            # Try Understat
            xg_df = self._fetch_understat_xg(league, season)
            if xg_df is not None and len(xg_df) > 0:
                df = self._merge_xg(df, xg_df, source='understat')
                logger.info(f"  Merged Understat xG for {len(xg_df)} matches")
                return df

            # Fallback: use actual goals
            logger.info(f"  No xG available, using actual goals")

        df = self._add_fallback_xg(df)
        return df

    # ── football-data.co.uk ─────────────────────

    def _fetch_football_data(self, league: str, season: str) -> Optional[pd.DataFrame]:
        """Fetch from football-data.co.uk."""
        cache_file = self.cache_dir / f"fd_{league}_{season}.csv"

        # Use cache if fresh (< 24h)
        if cache_file.exists():
            age = datetime.now().timestamp() - cache_file.stat().st_mtime
            if age < 86400:
                return pd.read_csv(cache_file)

        url = self.FD_BASE_URL.format(season=season, league=league)
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            cache_file.write_bytes(resp.content)
            df = pd.read_csv(StringIO(resp.content.decode('latin-1')))

            # Clean
            required = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']
            available = [c for c in required if c in df.columns]
            if len(available) < 5:
                return None

            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['FTHG', 'FTAG', 'Date'])
            df['FTHG'] = df['FTHG'].astype(int)
            df['FTAG'] = df['FTAG'].astype(int)

            if 'FTR' not in df.columns:
                df['FTR'] = df.apply(
                    lambda r: 'H' if r['FTHG'] > r['FTAG'] else ('A' if r['FTAG'] > r['FTHG'] else 'D'),
                    axis=1)

            return df

        except Exception as e:
            logger.warning(f"football-data.co.uk error: {e}")
            return None

    def _extract_fd_xg(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract xG from football-data columns if available."""
        # Some seasons have AvgxHG/AvgxAG or xHG/xAG
        if 'AvgxHG' in df.columns:
            df['xHG'] = df['AvgxHG'].astype(float)
            df['xAG'] = df['AvgxAG'].astype(float)
        elif 'xHG' not in df.columns:
            df['xHG'] = df['FTHG'].astype(float)
            df['xAG'] = df['FTAG'].astype(float)

        df['xg_source'] = 'football-data'
        # Fill any NaN xG with actual goals
        df['xHG'] = df['xHG'].fillna(df['FTHG'].astype(float))
        df['xAG'] = df['xAG'].fillna(df['FTAG'].astype(float))
        return df

    # ── Understat ────────────────────────────────

    def _fetch_understat_xg(self, league: str, season: str) -> Optional[pd.DataFrame]:
        """
        Fetch xG from Understat (free, no API key).
        Returns DataFrame with: HomeTeam, AwayTeam, xHG, xAG, Date
        """
        understat_league = self.UNDERSTAT_LEAGUES.get(league)
        if not understat_league:
            return None

        # Convert season '2526' to '2025'
        year = int('20' + season[:2])
        cache_file = self.cache_dir / f"understat_{league}_{year}.json"

        if cache_file.exists():
            age = datetime.now().timestamp() - cache_file.stat().st_mtime
            if age < 86400:
                with open(cache_file) as f:
                    data = json.load(f)
                return self._parse_understat(data)

        url = f"https://understat.com/league/{understat_league}/{year}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            # Understat embeds JSON in the page
            match = re.search(r"var datesData\s*=\s*JSON\.parse\('(.+?)'\)", resp.text)
            if not match:
                return None

            json_str = match.group(1)
            # Decode unicode escapes
            json_str = json_str.encode().decode('unicode_escape')
            data = json.loads(json_str)

            cache_file.write_text(json.dumps(data))
            return self._parse_understat(data)

        except Exception as e:
            logger.warning(f"Understat error for {league}: {e}")
            return None

    def _parse_understat(self, data: List[Dict]) -> pd.DataFrame:
        """Parse Understat JSON match data."""
        records = []
        for match in data:
            if not match.get('isResult', False):
                continue
            try:
                records.append({
                    'HomeTeam': match['h']['title'],
                    'AwayTeam': match['a']['title'],
                    'xHG': float(match['xG']['h']),
                    'xAG': float(match['xG']['a']),
                    'Date': pd.to_datetime(match['datetime']),
                    'xg_source': 'understat',
                })
            except (KeyError, ValueError):
                continue

        return pd.DataFrame(records) if records else None

    # ── Merge & Fallback ─────────────────────────

    def _merge_xg(self, base_df: pd.DataFrame, xg_df: pd.DataFrame,
                  source: str = 'external') -> pd.DataFrame:
        """
        Merge xG data into the base match DataFrame.
        Uses fuzzy team name matching + date proximity.
        """
        base_df = base_df.copy()
        base_df['xHG'] = np.nan
        base_df['xAG'] = np.nan
        base_df['xg_source'] = 'actual_goals'

        # Build lookup by date
        for idx, row in base_df.iterrows():
            match_date = row['Date']
            home = str(row['HomeTeam']).lower()
            away = str(row['AwayTeam']).lower()

            # Find matching xG row (same day, fuzzy team names)
            candidates = xg_df[
                (xg_df['Date'].dt.date == match_date.date()) if hasattr(match_date, 'date') else True
            ]

            for _, xg_row in candidates.iterrows():
                xg_home = str(xg_row['HomeTeam']).lower()
                xg_away = str(xg_row['AwayTeam']).lower()

                if (self._fuzzy_match(home, xg_home) and
                    self._fuzzy_match(away, xg_away)):
                    base_df.at[idx, 'xHG'] = xg_row['xHG']
                    base_df.at[idx, 'xAG'] = xg_row['xAG']
                    base_df.at[idx, 'xg_source'] = source
                    break

        # Fill missing xG with actual goals
        base_df['xHG'] = base_df['xHG'].fillna(base_df['FTHG'].astype(float))
        base_df['xAG'] = base_df['xAG'].fillna(base_df['FTAG'].astype(float))

        return base_df

    def _add_fallback_xg(self, df: pd.DataFrame) -> pd.DataFrame:
        """When no xG source available, use actual goals."""
        df = df.copy()
        df['xHG'] = df['FTHG'].astype(float)
        df['xAG'] = df['FTAG'].astype(float)
        df['xg_source'] = 'actual_goals'
        return df

    def _fuzzy_match(self, name1: str, name2: str) -> bool:
        """Simple fuzzy team name matching."""
        if name1 == name2:
            return True

        # Remove common prefixes/suffixes
        for remove in ['fc ', ' fc', 'sc ', ' sc', '1. ', 'real ', 'sporting ']:
            name1 = name1.replace(remove, '')
            name2 = name2.replace(remove, '')

        # Check substring
        if name1 in name2 or name2 in name1:
            return True

        # Check word overlap
        words1 = set(name1.split())
        words2 = set(name2.split())
        if len(words1 & words2) > 0:
            return True

        return False

    # ── Team Name Normalization ──────────────────

    # Understat → football-data.co.uk mappings (most common mismatches)
    TEAM_ALIASES = {
        # German
        'Bayern Munich': 'Bayern Munich', 'Bayer Leverkusen': 'Leverkusen',
        'Borussia Dortmund': 'Dortmund', 'Borussia M.Gladbach': "M'gladbach",
        'RB Leipzig': 'RB Leipzig', 'Eintracht Frankfurt': 'Ein Frankfurt',
        # English
        'Manchester City': 'Man City', 'Manchester United': 'Man United',
        'Wolverhampton Wanderers': 'Wolves', 'Nottingham Forest': "Nott'm Forest",
        'Brighton and Hove Albion': 'Brighton', 'West Ham United': 'West Ham',
        'Newcastle United': 'Newcastle', 'Tottenham Hotspur': 'Tottenham',
        # Spanish
        'Atletico Madrid': 'Ath Madrid', 'Athletic Club': 'Ath Bilbao',
        'Real Betis': 'Betis', 'Celta Vigo': 'Celta',
        # Italian
        'AC Milan': 'Milan', 'Inter Milan': 'Inter',
        'Hellas Verona': 'Verona',
        # French
        'Paris Saint Germain': 'Paris SG', 'Olympique Lyonnais': 'Lyon',
        'Olympique Marseille': 'Marseille', 'AS Monaco': 'Monaco',
    }


# Singleton
xg_fetcher = XGDataFetcher()

if __name__ == "__main__":
    fetcher = XGDataFetcher()
    print("Testing xG data fetch for Bundesliga...")
    df = fetcher.fetch_training_data('D1', seasons=1)
    if not df.empty:
        print(f"\nLoaded {len(df)} matches")
        print(f"xG sources: {df['xg_source'].value_counts().to_dict()}")
        print(f"\nSample:")
        cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'xHG', 'xAG', 'xg_source']
        available = [c for c in cols if c in df.columns]
        print(df[available].tail(5))
    else:
        print("No data fetched")

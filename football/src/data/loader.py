"""football-data.co.uk loader for training scripts."""
from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List

import pandas as pd
import requests


class FootballDataLoader:
    BASE_URL = 'https://www.football-data.co.uk/mmz4281/{season}/{league}.csv'

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path('data/training_cache')
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _season_code(self, start_year: int) -> str:
        return f"{str(start_year)[2:]}{str(start_year + 1)[2:]}"

    def download_season(self, league_code: str, start_year: int) -> pd.DataFrame:
        season = self._season_code(start_year)
        cache = self.data_dir / f'{league_code}_{season}.csv'
        if cache.exists():
            return pd.read_csv(cache)
        url = self.BASE_URL.format(season=season, league=league_code)
        resp = requests.get(url, timeout=45)
        resp.raise_for_status()
        cache.write_bytes(resp.content)
        return pd.read_csv(StringIO(resp.content.decode('latin-1')))

    def process_match_data(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        keep = [c for c in ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'xHG', 'xAG'] if c in df.columns]
        df = df[keep].dropna(subset=['HomeTeam', 'AwayTeam'])
        if 'FTHG' in df.columns and 'FTAG' in df.columns:
            df = df.dropna(subset=['FTHG', 'FTAG'])
        return df.reset_index(drop=True)

    def load_training_data(self, leagues: List[str] | None = None, seasons: int = 3) -> pd.DataFrame:
        leagues = leagues or ['D1']
        year = datetime.now().year - 1 if datetime.now().month < 7 else datetime.now().year
        frames = []
        for league in leagues:
            for offset in range(seasons):
                try:
                    raw = self.download_season(league, year - offset)
                    proc = self.process_match_data(raw)
                    if not proc.empty:
                        proc['League'] = league
                        frames.append(proc)
                except Exception:
                    continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

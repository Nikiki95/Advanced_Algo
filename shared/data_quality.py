"""Basic data-quality and validation helpers."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


def normalize_team_name(name: str) -> str:
    text = (name or '').lower().strip()
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    for token in ['fc', 'cf', 'sc', 'sv', 'club', 'the']:
        text = re.sub(rf'{token}', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    aliases = {
        'bayern munich': 'bayern munchen',
        'borussia dortmund': 'dortmund',
        'los angeles lakers': 'lal',
        'golden state warriors': 'golden state',
    }
    return aliases.get(text, text)


def event_key(home_team: str, away_team: str, commence_time: Optional[str]) -> str:
    return '|'.join([
        normalize_team_name(home_team),
        normalize_team_name(away_team),
        str(commence_time or '')[:19],
    ])


@dataclass
class ValidationIssue:
    level: str
    code: str
    message: str
    context: Dict = field(default_factory=dict)


def validate_odds_value(value) -> bool:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and 1.01 <= value <= 101.0


def validate_dataframe(df: pd.DataFrame, required_cols: Sequence[str],
                       odds_cols: Sequence[str] = ()) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        issues.append(ValidationIssue('error', 'missing_columns',
                                      f"Missing required columns: {', '.join(missing)}"))
        return issues

    if {'home_team', 'away_team'}.issubset(df.columns):
        dupes = df.duplicated(subset=['home_team', 'away_team', *([c for c in ['commence_time', 'match_date'] if c in df.columns])])
        if dupes.any():
            issues.append(ValidationIssue('warning', 'duplicate_games',
                                          f"Detected {int(dupes.sum())} duplicate rows"))

    for col in odds_cols:
        if col not in df.columns:
            continue
        bad = df[col].apply(lambda x: x is not None and x != '' and not validate_odds_value(x))
        if bad.any():
            issues.append(ValidationIssue('warning', 'invalid_odds',
                                          f"Column {col} contains {int(bad.sum())} invalid odds values"))
    return issues


def dedupe_games(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or 'home_team' not in df.columns or 'away_team' not in df.columns:
        return df
    subset = ['home_team', 'away_team']
    if 'commence_time' in df.columns:
        subset.append('commence_time')
    elif 'match_date' in df.columns:
        subset.append('match_date')
    return df.drop_duplicates(subset=subset, keep='first').reset_index(drop=True)


def validate_bet_payload(bet: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for key in ['sport', 'home_team', 'away_team', 'selection', 'market']:
        if not bet.get(key):
            issues.append(ValidationIssue('error', 'missing_field', f"Bet missing {key}"))
    if not validate_odds_value(bet.get('odds')):
        issues.append(ValidationIssue('error', 'bad_odds', 'Bet has invalid odds', {'odds': bet.get('odds')}))
    return issues

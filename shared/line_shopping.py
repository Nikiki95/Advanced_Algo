"""Helpers for bookmaker option tracking and best-line selection."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple


def options_from_mapping(mapping: Optional[Dict[str, float]]) -> List[Dict]:
    if not mapping:
        return []
    options = []
    for bookmaker, odds in mapping.items():
        try:
            odds_f = float(odds)
        except (TypeError, ValueError):
            continue
        options.append({"bookmaker": bookmaker, "odds": odds_f})
    return sorted(options, key=lambda x: x["odds"], reverse=True)


def best_option(mapping: Optional[Dict[str, float]]) -> Tuple[str, float, List[Dict]]:
    options = options_from_mapping(mapping)
    if not options:
        return "", 0.0, []
    best = options[0]
    return best["bookmaker"], best["odds"], options


def summarize_options(options: Iterable[Dict], limit: int = 5) -> List[Dict]:
    cleaned = []
    for row in list(options)[:limit]:
        if not isinstance(row, dict):
            continue
        bookmaker = row.get("bookmaker") or row.get("key") or row.get("name")
        odds = row.get("odds") or row.get("price")
        try:
            odds = float(odds)
        except (TypeError, ValueError):
            continue
        cleaned.append({"bookmaker": str(bookmaker), "odds": odds})
    return cleaned


def best_from_options(options: Iterable[Dict]) -> Tuple[str, float, List[Dict]]:
    summarized = summarize_options(options, limit=20)
    if not summarized:
        return "", 0.0, []
    best = max(summarized, key=lambda x: x["odds"])
    return best["bookmaker"], best["odds"], summarized

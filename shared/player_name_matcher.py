"""Helpers for robust player/team name normalization and matching."""
from __future__ import annotations

import unicodedata
from typing import Optional


def normalize_text(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    substitutions = {
        '&': 'and',
        '.': ' ',
        ',': ' ',
        '-': ' ',
        "'": '',
        '/': ' ',
    }
    for old, new in substitutions.items():
        text = text.replace(old, new)
    text = ' '.join(text.split())
    return text


def normalize_team(value: str) -> str:
    text = f' {normalize_text(value)} '
    for token in ('fc', 'cf', 'ac', 'bc', 'club', 'the', 'sc', 'sv'):
        text = text.replace(f' {token} ', ' ')
    aliases = {
        'manchester united': 'man united',
        'manchester city': 'man city',
        'internazionale': 'inter',
        'paris saint germain': 'psg',
        'borussia dortmund': 'dortmund',
        'bayern munchen': 'bayern munich',
        'sporting lisbon': 'sporting cp',
        'internazionale milano': 'inter',
    }
    text = ' '.join(text.split())
    return aliases.get(text, text)


def normalize_person(value: str) -> str:
    text = f' {normalize_text(value)} '
    suffixes = (' jr ', ' sr ', ' iii ', ' ii ', ' iv ', ' v ')
    for suffix in suffixes:
        text = text.replace(suffix, ' ')
    text = ' '.join(text.split())
    aliases = {
        'odell beckham junior': 'odell beckham',
    }
    return aliases.get(text, text)


def team_match_score(candidate: str, target: str) -> Optional[int]:
    cand = normalize_team(candidate)
    targ = normalize_team(target)
    if not cand or not targ:
        return None
    if targ not in cand and cand not in targ:
        return None
    return abs(len(cand) - len(targ))


def person_match_score(candidate: str, target: str) -> Optional[int]:
    cand = normalize_person(candidate)
    targ = normalize_person(target)
    if not cand or not targ:
        return None
    if targ == cand:
        return 0
    if targ not in cand and cand not in targ:
        cand_parts = set(cand.split())
        targ_parts = set(targ.split())
        overlap = cand_parts & targ_parts
        if len(overlap) < max(1, min(len(cand_parts), len(targ_parts)) - 1):
            return None
    return abs(len(cand) - len(targ))

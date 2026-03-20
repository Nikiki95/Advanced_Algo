"""Snapshot observed odds over time and derive closing lines for tracked bets."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional

from .runtime_utils import data_root, ensure_parent, now_iso, safe_float


def _normalize(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


class ClosingLineManager:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or data_root() / "closing_lines"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sport: str) -> Path:
        return self.root / f"{sport}_snapshots.jsonl"

    def record_snapshot(self, sport: str, event: Dict, captured_at: Optional[str] = None):
        captured_at = captured_at or now_iso()
        path = self._path(sport)
        ensure_parent(path)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"captured_at": captured_at, **event}) + "\n")

    def record_candidates(
        self,
        sport: str,
        home_team: str,
        away_team: str,
        match_date: str,
        event_id: str,
        market_rows: Iterable[Dict],
    ):
        for row in market_rows:
            payload = {
                "event_id": event_id,
                "home_team": home_team,
                "away_team": away_team,
                "match_date": match_date,
                **row,
            }
            self.record_snapshot(sport, payload)

    def lookup_closing_odds(self, bet: Dict) -> Optional[Dict]:
        path = self._path(bet.get("sport", "unknown"))
        if not path.exists():
            return None
        try:
            match_dt = datetime.fromisoformat(str(bet.get("match_date")).replace("Z", "+00:00"))
            window_end = match_dt + timedelta(minutes=5)
        except Exception:
            match_dt = None
            window_end = None
        target_market = _normalize(bet.get("market") or bet.get("bet_type"))
        target_selection = _normalize(bet.get("selection"))
        candidates = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if _normalize(row.get("home_team")) != _normalize(bet.get("home_team")) or _normalize(row.get("away_team")) != _normalize(bet.get("away_team")):
                continue
            if _normalize(row.get("market")) != target_market or _normalize(row.get("selection")) != target_selection:
                continue
            if match_dt and row.get("captured_at"):
                try:
                    captured = datetime.fromisoformat(str(row["captured_at"]).replace("Z", "+00:00"))
                except Exception:
                    continue
                if captured > window_end:
                    continue
            else:
                captured = datetime.min.replace(tzinfo=timezone.utc)
            candidates.append((captured, row))
        if not candidates:
            return None
        _, row = sorted(candidates, key=lambda x: x[0])[-1]
        return {
            "closing_odds": safe_float(row.get("odds")),
            "closing_bookmaker": row.get("bookmaker"),
            "captured_at": row.get("captured_at"),
        }

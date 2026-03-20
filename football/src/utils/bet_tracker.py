"""Football wrapper around the universal V3 bet tracker."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.feedback_loop import UniversalBetTracker as BetTracker  # noqa: E402


tracker = BetTracker()

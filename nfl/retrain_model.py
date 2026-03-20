#!/usr/bin/env python3
"""NFL retraining wrapper for V3 orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nfl_analyzer import train_model


def main():
    model = train_model(weeks_back=17)
    if model is None:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

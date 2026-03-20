#!/usr/bin/env python3
"""CLI wrapper for the shared prop-settlement pipeline."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from shared.prop_settlement import main

if __name__ == "__main__":
    main()

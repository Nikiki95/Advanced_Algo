"""Promotion rules for candidate models."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from .runtime_utils import data_root, ensure_parent, now_iso


class DeploymentGate:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_root() / "model_registry" / "gate_reports.jsonl"

    def evaluate(
        self,
        sport: str,
        candidate: Dict,
        current: Optional[Dict] = None,
        recent_perf: Optional[Dict] = None,
    ) -> Dict:
        metrics = dict(candidate.get("metrics") or {})
        if recent_perf:
            metrics.setdefault("recent_roi_percent", recent_perf.get("roi_percent", 0))
            metrics.setdefault("recent_clv_percent", recent_perf.get("clv", {}).get("avg_clv_percent", 0))
            metrics.setdefault("recent_bets", recent_perf.get("total_bets", 0))
            metrics.setdefault("recent_drawdown_percent", recent_perf.get("max_drawdown_percent", 0))

        current_metrics = (current or {}).get("metrics", {})
        reasons = []
        passed = True

        min_bets = 20
        roi = float(metrics.get("recent_roi_percent", metrics.get("roi_percent", 0)))
        clv = float(metrics.get("recent_clv_percent", metrics.get("avg_clv_percent", 0)))
        bets = int(metrics.get("recent_bets", metrics.get("sample_size", 0)))
        drawdown = float(metrics.get("recent_drawdown_percent", metrics.get("max_drawdown_percent", 0)))
        current_roi = (
            float(current_metrics.get("recent_roi_percent", current_metrics.get("roi_percent", 0)))
            if current
            else None
        )

        if bets < min_bets:
            passed = False
            reasons.append(f"not enough graded bets ({bets} < {min_bets})")
        if roi < -2:
            passed = False
            reasons.append(f"roi below gate ({roi:.2f}%)")
        if clv < -0.5:
            passed = False
            reasons.append(f"clv below gate ({clv:.2f}%)")
        if drawdown < -15:
            passed = False
            reasons.append(f"drawdown too deep ({drawdown:.2f}%)")
        if current_roi is not None and roi < current_roi - 1.0:
            passed = False
            reasons.append(f"candidate under current active model ({roi:.2f}% < {current_roi:.2f}%)")

        report = {
            "timestamp": now_iso(),
            "sport": sport,
            "candidate_version": candidate.get("model_version"),
            "current_version": (current or {}).get("model_version"),
            "passed": passed,
            "reasons": reasons or ["passed"],
            "metrics": metrics,
        }
        ensure_parent(self.path)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(report) + "\n")
        return report

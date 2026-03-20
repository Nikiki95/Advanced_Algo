"""Central retraining entrypoint with model registration and gating."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict

from .deployment_gate import DeploymentGate
from .feedback_loop import UniversalBetTracker
from .model_registry import ModelRegistry
from .runtime_utils import project_root


TRAINING_COMMANDS = {
    'football': [sys.executable, 'football/train_all_leagues.py', '--all', '--force'],
    'nba': [sys.executable, 'nba/retrain_model.py'],
    'nfl': [sys.executable, 'nfl/retrain_model.py'],
    'euroleague': [sys.executable, 'euroleague/retrain_model.py'],
    'tennis': [sys.executable, 'tennis/retrain_model.py'],
}

MODEL_GLOBS = {
    'football': 'football/models/leagues/*.pkl',
    'nba': 'nba/models/*.pkl',
    'nfl': 'nfl/models/*.pkl',
    'euroleague': 'euroleague/models/*.json',
    'tennis': 'tennis/models/*.json',
}


def latest_model_file(pattern: str) -> Path | None:
    files = sorted(project_root().glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def retrain_sport(sport: str) -> Dict:
    tracker = UniversalBetTracker()
    perf = tracker.calculate_performance(days=60, sport=sport)
    registry = ModelRegistry()
    gate = DeploymentGate()
    report = {'sport': sport, 'returncode': 0, 'stdout_tail': '', 'stderr_tail': ''}
    cmd = TRAINING_COMMANDS.get(sport)
    if cmd:
        proc = subprocess.run(cmd, cwd=project_root(), capture_output=True, text=True)
        report.update({'returncode': proc.returncode, 'stdout_tail': proc.stdout[-2000:], 'stderr_tail': proc.stderr[-2000:]})
    model_file = latest_model_file(MODEL_GLOBS.get(sport, '')) if MODEL_GLOBS.get(sport) else None
    if model_file:
        candidate = registry.ensure_registered_from_file(sport, model_file)
        active = registry.get_active(sport)
        gate_report = gate.evaluate(sport, candidate, current=active, recent_perf=perf)
        report['gate_report'] = gate_report
        if gate_report.get('passed'):
            registry.set_active(sport, candidate['model_version'], reason='retrain-pass')
    return report


def main():
    parser = argparse.ArgumentParser(description='Retrain orchestrator for Betting Algorithm V6')
    parser.add_argument('--sport', choices=['football', 'nba', 'nfl', 'euroleague', 'tennis', 'all'], default='all')
    args = parser.parse_args()
    sports = ['football', 'nba', 'nfl', 'euroleague', 'tennis'] if args.sport == 'all' else [args.sport]
    for sport in sports:
        result = retrain_sport(sport)
        status = '✅' if result['returncode'] == 0 else '❌'
        print(f"{status} {sport}: rc={result['returncode']}")
        if result.get('gate_report'):
            print(f"   gate: {'PASS' if result['gate_report']['passed'] else 'HOLD'}")


if __name__ == '__main__':
    main()

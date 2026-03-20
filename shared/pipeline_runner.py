#!/usr/bin/env python3
"""Central runner for daily/weekly/UEFA/props pipelines."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

if __package__ in (None, ''):
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from shared.pipeline_presets import PIPELINE_PRESETS
    from shared.runtime_utils import data_root, now_iso, project_root
else:
    from .pipeline_presets import PIPELINE_PRESETS
    from .runtime_utils import data_root, now_iso, project_root


def run_pipeline(name: str, continue_on_error: bool = False) -> Dict:
    commands = PIPELINE_PRESETS[name]
    runs: List[Dict] = []
    for command in commands:
        proc = subprocess.run(command, cwd=project_root(), capture_output=True, text=True)
        entry = {
            'command': command,
            'returncode': proc.returncode,
            'stdout_tail': proc.stdout[-4000:],
            'stderr_tail': proc.stderr[-4000:],
        }
        runs.append(entry)
        if proc.returncode != 0 and not continue_on_error:
            break
    payload = {
        'pipeline': name,
        'timestamp': now_iso(),
        'commands': runs,
        'success': all(r['returncode'] == 0 for r in runs),
    }
    out_dir = data_root() / 'pipeline_runs'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{name}.json'
    out_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run a named Betting Algorithm pipeline preset')
    parser.add_argument('pipeline', choices=sorted(PIPELINE_PRESETS.keys()))
    parser.add_argument('--continue-on-error', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    result = run_pipeline(args.pipeline, continue_on_error=args.continue_on_error)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        ok = 'OK' if result['success'] else 'FAILED'
        print(f"Pipeline {args.pipeline}: {ok} ({len(result['commands'])} commands)")
        for item in result['commands']:
            print(f" - rc={item['returncode']} :: {' '.join(item['command'])}")


if __name__ == '__main__':
    main()

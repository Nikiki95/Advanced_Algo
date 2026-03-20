#!/usr/bin/env bash
set -euo pipefail
python -m shared.pipeline_runner daily "$@"

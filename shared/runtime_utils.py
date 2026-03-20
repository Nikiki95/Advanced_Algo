"""Runtime helpers shared across scripts."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_root() -> Path:
    path = project_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_env() -> Path:
    env_path = project_root() / "secrets" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())
    return env_path


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    safe = ''.join(ch.lower() if ch.isalnum() else '-' for ch in str(value))
    while '--' in safe:
        safe = safe.replace('--', '-')
    return safe.strip('-') or 'unknown'


def canonical_event_key(sport: str, home_team: str, away_team: str, match_date: Optional[str]) -> str:
    match_date = (match_date or '')[:19]
    raw = f"{sport}|{home_team}|{away_team}|{match_date}".lower()
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]
    return f"{slugify(sport)}-{digest}"


def import_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if not spec or not spec.loader:
        raise ImportError(f"Cannot import {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def json_default(value: Any):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def chunked(iterable: Iterable[Any], size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

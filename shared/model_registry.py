"""Simple model registry for candidate and active model versions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .runtime_utils import data_root, ensure_parent, now_iso, slugify


class ModelRegistry:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_root() / 'model_registry' / 'registry.json'
        self.registry = self.load()

    def load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                pass
        return {'active': {}, 'candidates': {}, 'history': []}

    def save(self):
        ensure_parent(self.path)
        self.path.write_text(json.dumps(self.registry, indent=2), encoding='utf-8')

    def register_candidate(self, sport: str, file_path: str, model_version: str,
                           feature_set_version: str = 'v3', metrics: Optional[Dict] = None,
                           tags: Optional[List[str]] = None) -> Dict:
        payload = {
            'sport': sport,
            'file_path': str(file_path),
            'model_version': model_version,
            'feature_set_version': feature_set_version,
            'metrics': metrics or {},
            'tags': tags or [],
            'registered_at': now_iso(),
        }
        self.registry.setdefault('candidates', {}).setdefault(sport, [])
        candidates = [c for c in self.registry['candidates'][sport] if c.get('model_version') != model_version]
        candidates.append(payload)
        self.registry['candidates'][sport] = candidates
        self.save()
        return payload

    def set_active(self, sport: str, model_version: str, reason: str = 'manual') -> Optional[Dict]:
        candidates = self.registry.get('candidates', {}).get(sport, [])
        candidate = next((c for c in candidates if c.get('model_version') == model_version), None)
        if not candidate:
            return None
        active_payload = dict(candidate)
        active_payload['activated_at'] = now_iso()
        active_payload['activation_reason'] = reason
        self.registry.setdefault('active', {})[sport] = active_payload
        self.registry.setdefault('history', []).append({'sport': sport, 'model_version': model_version, 'reason': reason, 'timestamp': now_iso()})
        self.save()
        return active_payload

    def get_active(self, sport: str) -> Optional[Dict]:
        return self.registry.get('active', {}).get(sport)

    def latest_candidate(self, sport: str) -> Optional[Dict]:
        candidates = self.registry.get('candidates', {}).get(sport, [])
        if not candidates:
            return None
        return sorted(candidates, key=lambda x: x.get('registered_at', ''))[-1]

    def ensure_registered_from_file(self, sport: str, file_path: Path,
                                    feature_set_version: str = 'v3') -> Dict:
        model_version = f"{slugify(sport)}-{file_path.stem}"
        candidate = self.register_candidate(sport, str(file_path), model_version,
                                            feature_set_version=feature_set_version,
                                            metrics={'file_mtime': file_path.stat().st_mtime})
        if not self.get_active(sport):
            self.set_active(sport, model_version, reason='bootstrap')
        return candidate

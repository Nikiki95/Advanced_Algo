#!/usr/bin/env python3
"""Telegram command bot that turns the existing alert chat into a simple control panel."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if __package__ in (None, ''):
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from shared.feedback_loop import UniversalBetTracker
    from shared.model_registry import ModelRegistry
    from shared.runtime_utils import data_root, load_env, now_iso, project_root
    from shared.telegram_bot import BettingAlertBot
else:
    from .feedback_loop import UniversalBetTracker
    from .model_registry import ModelRegistry
    from .runtime_utils import data_root, load_env, now_iso, project_root
    from .telegram_bot import BettingAlertBot


@dataclass
class JobState:
    name: str
    command: List[str]
    requested_by: str
    requested_at: str
    log_path: str
    status: str = 'running'
    process_pid: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    returncode: Optional[int] = None


class TelegramControlBot:
    def __init__(self):
        load_env()
        self.alert_bot = BettingAlertBot()
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = str(os.getenv('TELEGRAM_CHAT_ID', '')).strip()
        self.allowed_user_ids = {
            x.strip() for x in os.getenv('TELEGRAM_ALLOWED_USER_IDS', '').split(',') if x.strip()
        }
        self.commands_enabled = os.getenv('TELEGRAM_COMMANDS_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on')
        self.poll_interval = max(float(os.getenv('TELEGRAM_POLL_INTERVAL', '3')), 1.0)
        self.max_runtime_minutes = int(os.getenv('TELEGRAM_MAX_RUNTIME_MINUTES', '120') or '120')
        self.root = project_root()
        self.state_dir = data_root() / 'telegram_control'
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.offset_path = self.state_dir / 'offset.txt'
        self.job_state_path = self.state_dir / 'current_job.json'
        self.job_history_path = self.state_dir / 'job_history.jsonl'
        self.log_dir = self.state_dir / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_process: Optional[subprocess.Popen] = None
        self.current_job: Optional[JobState] = None
        self._restore_job_state()

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id and self.commands_enabled)

    def api_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        params = params or {}
        base = f'https://api.telegram.org/bot{self.bot_token}/{method}'
        if method == 'getUpdates':
            query = urlencode(params)
            req = Request(f'{base}?{query}')
            with urlopen(req, timeout=65) as resp:
                return json.loads(resp.read().decode('utf-8'))
        payload = json.dumps(params).encode('utf-8')
        req = Request(base, data=payload, headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def get_offset(self) -> int:
        try:
            return int(self.offset_path.read_text(encoding='utf-8').strip())
        except Exception:
            return 0

    def save_offset(self, offset: int):
        self.offset_path.write_text(str(offset), encoding='utf-8')

    def _restore_job_state(self):
        if not self.job_state_path.exists():
            return
        try:
            payload = json.loads(self.job_state_path.read_text(encoding='utf-8'))
            self.current_job = JobState(**payload)
            pid = self.current_job.process_pid
            if pid and self._pid_running(pid):
                self.current_process = None
            else:
                self.current_job.status = 'unknown'
        except Exception:
            self.current_job = None

    def _pid_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _save_current_job(self):
        if not self.current_job:
            if self.job_state_path.exists():
                self.job_state_path.unlink()
            return
        self.job_state_path.write_text(json.dumps(asdict(self.current_job), indent=2), encoding='utf-8')

    def _append_job_history(self, payload: Dict):
        with self.job_history_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload) + '\n')

    def _authorized(self, msg: Dict) -> bool:
        chat = msg.get('chat') or {}
        from_user = msg.get('from') or {}
        if self.chat_id and str(chat.get('id')) != self.chat_id:
            return False
        if self.allowed_user_ids and str(from_user.get('id')) not in self.allowed_user_ids:
            return False
        return True

    def _display_user(self, msg: Dict) -> str:
        user = msg.get('from') or {}
        return user.get('username') or user.get('first_name') or str(user.get('id') or 'unknown')

    def _reply(self, text: str, markdown: bool = False):
        if markdown:
            self.alert_bot.send_sync(text, parse_mode='Markdown')
        else:
            self.alert_bot.send_plain(text)

    def _tail(self, path: Path, max_chars: int = 3000) -> str:
        if not path.exists():
            return 'Noch kein Log vorhanden.'
        raw = path.read_text(encoding='utf-8', errors='ignore')
        return raw[-max_chars:] if raw else 'Log ist leer.'

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _format_bet_line(self, bet: Dict) -> str:
        sport = (bet.get('sport') or '?').upper()
        league = bet.get('league') or '-'
        event = f"{bet.get('home_team', '?')} vs {bet.get('away_team', '?')}"
        market = bet.get('market') or bet.get('bet_type') or '-'
        selection = bet.get('selection') or bet.get('player_name') or '-'
        odds = self._safe_float(bet.get('odds'), 0.0)
        stamp = str(bet.get('timestamp') or '-')[:19].replace('T', ' ')
        result = bet.get('actual_result')
        profit = bet.get('profit_loss')
        suffix = ''
        if result is not None:
            suffix = f" | {result}"
            if profit is not None:
                suffix += f" {self._safe_float(profit):+.2f}"
        return f"- [{sport}/{league}] {event} | {market}: {selection} @ {odds:.2f} | {stamp}{suffix}"

    def _latest_bets_summary(self, limit: int = 5) -> str:
        tracker = UniversalBetTracker()
        active = sorted(tracker.get_active_bets(), key=lambda r: r.get('timestamp') or '', reverse=True)[:limit]
        settled = sorted(tracker.get_settled_bets(days=30), key=lambda r: r.get('settled_at') or r.get('timestamp') or '', reverse=True)[:limit]
        parts = ['Letzte Bets']
        if active:
            parts.append('\nAktiv:')
            parts.extend(self._format_bet_line(b) for b in active)
        else:
            parts.append('\nAktiv: keine')
        if settled:
            parts.append('\nZuletzt settled:')
            parts.extend(self._format_bet_line(b) for b in settled)
        else:
            parts.append('\nZuletzt settled: keine')
        return '\n'.join(parts)

    def _performance_summary(self, sport: str = 'all', days: int = 30) -> str:
        tracker = UniversalBetTracker()
        sport = sport.lower().strip() or 'all'
        if sport == 'all':
            sport_filter = None
        elif sport in ('football', 'nba', 'nfl', 'euroleague', 'tennis'):
            sport_filter = sport
        else:
            return 'Ungültiger Sport für /performance. Erlaubt: all, football, nba, nfl, euroleague, tennis'
        days = max(1, min(days, 365))
        perf = tracker.calculate_performance(days=days, sport=sport_filter)
        lines = [
            f"Performance {sport_filter or 'all'} / {days}d",
            f"Bets: {perf.get('total_bets', 0)} | W: {perf.get('wins', 0)} | L: {perf.get('losses', 0)} | V/P: {perf.get('voids', 0)}",
            f"Win-Rate: {self._safe_float(perf.get('win_rate')):.2f}%",
            f"ROI: {self._safe_float(perf.get('roi_percent')):+.2f}%",
            f"Profit: {self._safe_float(perf.get('total_profit')):+.2f}",
            f"Staked: {self._safe_float(perf.get('total_staked')):.2f}",
            f"Avg Value: {self._safe_float(perf.get('avg_value_percent')):.2f}%",
            f"Max DD: {self._safe_float(perf.get('max_drawdown_percent')):.2f}%",
        ]
        clv = perf.get('clv') or {}
        if clv.get('available'):
            lines.append(
                f"CLV: {self._safe_float(clv.get('avg_clv_percent')):+.2f}% | positive: {self._safe_float(clv.get('positive_clv_rate')):.2f}%"
            )
        league_perf = perf.get('league_performance') or {}
        if league_perf:
            top = sorted(league_perf.items(), key=lambda kv: self._safe_float(kv[1].get('profit')), reverse=True)[:5]
            lines.append('Top Ligen: ' + '; '.join(
                f"{league}: {self._safe_float(stats.get('profit')):+.2f} ({self._safe_float(stats.get('roi_percent')):+.2f}% / {int(stats.get('bets', 0))} Bets)"
                for league, stats in top
            ))
        market_perf = perf.get('market_performance') or {}
        if market_perf:
            top_m = sorted(market_perf.items(), key=lambda kv: self._safe_float(kv[1].get('profit')), reverse=True)[:5]
            lines.append('Top Märkte: ' + '; '.join(
                f"{market}: {self._safe_float(stats.get('profit')):+.2f} ({int(stats.get('bets', 0))} Bets, WR {self._safe_float(stats.get('win_rate')):.1f}%)"
                for market, stats in top_m
            ))
        return '\n'.join(lines)

    def _read_job_history(self, limit: int = 5) -> List[Dict]:
        if not self.job_history_path.exists():
            return []
        rows: List[Dict] = []
        for raw in self.job_history_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        rows.sort(
            key=lambda item: item.get('finished_at') or item.get('started_at') or item.get('requested_at') or '',
            reverse=True,
        )
        return rows[:limit]

    def _jobs_summary(self, limit: int = 5) -> str:
        limit = max(1, min(limit, 10))
        lines = ['Jobs']
        if self._job_running() and self.current_job:
            lines.append(
                f"Aktiv: {self.current_job.name} | PID {self.current_job.process_pid} | seit {self.current_job.started_at} | von {self.current_job.requested_by}"
            )
            lines.append(f"Log: {Path(self.current_job.log_path).relative_to(self.root)}")
        else:
            lines.append('Aktiv: keiner')
        recent = self._read_job_history(limit=limit)
        if recent:
            lines.append('')
            lines.append('Letzte Jobläufe:')
            for item in recent:
                name = item.get('name', 'unknown')
                status = item.get('status', '?')
                rc = item.get('returncode')
                when = (item.get('finished_at') or item.get('started_at') or item.get('requested_at') or '-')[:19].replace('T', ' ')
                requester = item.get('requested_by', '?')
                lines.append(f"- {when} | {name} | {status} | rc={rc} | {requester}")
        else:
            lines.append('')
            lines.append('Noch keine Job-Historie vorhanden.')
        return '\n'.join(lines)

    def _history_summary(self, limit: int = 5) -> str:
        limit = max(1, min(limit, 10))
        lines = ['History']
        pipeline_dir = data_root() / 'pipeline_runs'
        pipeline_files = sorted(pipeline_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        if pipeline_files:
            lines.append('Letzte Pipelines:')
            for path in pipeline_files:
                try:
                    payload = json.loads(path.read_text(encoding='utf-8'))
                    ok = 'OK' if payload.get('success') else 'FAIL'
                    cmd_count = len(payload.get('commands') or [])
                    stamp = str(payload.get('timestamp') or '-')[:19].replace('T', ' ')
                    lines.append(f"- {stamp} | {payload.get('pipeline', path.stem)} | {ok} | {cmd_count} steps")
                except Exception:
                    lines.append(f"- {path.stem} | unreadable")
        else:
            lines.append('Letzte Pipelines: keine')
        registry = ModelRegistry()
        model_hist = list(reversed(registry.registry.get('history', [])))[:limit]
        if model_hist:
            lines.append('')
            lines.append('Letzte Modell-Aktivierungen:')
            for item in model_hist:
                stamp = str(item.get('timestamp') or '-')[:19].replace('T', ' ')
                lines.append(
                    f"- {stamp} | {item.get('sport', '?')} -> {item.get('model_version', '?')} ({item.get('reason', '-')})"
                )
        else:
            lines.append('')
            lines.append('Letzte Modell-Aktivierungen: keine')
        return '\n'.join(lines)

    def _models_summary(self, sport: str = 'all') -> str:
        sport = (sport or 'all').lower().strip()
        allowed = ('all', 'football', 'nba', 'nfl', 'euroleague', 'tennis')
        if sport not in allowed:
            return 'Ungültiger Sport für /models. Erlaubt: all, football, nba, nfl, euroleague, tennis'
        registry = ModelRegistry()
        active = registry.registry.get('active', {})
        candidates = registry.registry.get('candidates', {})
        sports = [sport] if sport != 'all' else sorted(set(active.keys()) | set(candidates.keys()))
        if not sports:
            return 'Keine Modelle im Registry gefunden.'
        lines = ['Models']
        for item_sport in sports:
            active_item = active.get(item_sport)
            latest = registry.latest_candidate(item_sport)
            lines.append('')
            lines.append(f'{item_sport}:')
            if active_item:
                metrics = active_item.get('metrics') or {}
                metric_bits = []
                if 'roi_percent' in metrics:
                    metric_bits.append(f"roi={self._safe_float(metrics.get('roi_percent')):+.2f}%")
                if 'total_profit' in metrics:
                    metric_bits.append(f"profit={self._safe_float(metrics.get('total_profit')):+.2f}")
                if 'win_rate' in metrics:
                    metric_bits.append(f"wr={self._safe_float(metrics.get('win_rate')):.2f}%")
                metric_text = f" | {'; '.join(metric_bits)}" if metric_bits else ''
                stamp = str(active_item.get('activated_at') or '-')[:19].replace('T', ' ')
                lines.append(
                    f"- aktiv: {active_item.get('model_version', 'n/a')} | feature-set {active_item.get('feature_set_version', 'n/a')} | seit {stamp}{metric_text}"
                )
            else:
                lines.append('- aktiv: keines')
            if latest:
                metrics = latest.get('metrics') or {}
                metric_bits = []
                if 'roi_percent' in metrics:
                    metric_bits.append(f"roi={self._safe_float(metrics.get('roi_percent')):+.2f}%")
                if 'total_profit' in metrics:
                    metric_bits.append(f"profit={self._safe_float(metrics.get('total_profit')):+.2f}")
                if 'win_rate' in metrics:
                    metric_bits.append(f"wr={self._safe_float(metrics.get('win_rate')):.2f}%")
                metric_text = f" | {'; '.join(metric_bits)}" if metric_bits else ''
                stamp = str(latest.get('registered_at') or '-')[:19].replace('T', ' ')
                lines.append(
                    f"- latest candidate: {latest.get('model_version', 'n/a')} | feature-set {latest.get('feature_set_version', 'n/a')} | reg {stamp}{metric_text}"
                )
                lines.append(f"- candidates gesamt: {len(candidates.get(item_sport, []))}")
            else:
                lines.append('- latest candidate: keiner')
        history = list(reversed(registry.registry.get('history', [])))[:5]
        if history:
            lines.append('')
            lines.append('Letzte Aktivierungen:')
            for item in history:
                stamp = str(item.get('timestamp') or '-')[:19].replace('T', ' ')
                lines.append(
                    f"- {stamp} | {item.get('sport', '?')} -> {item.get('model_version', '?')} ({item.get('reason', '-')})"
                )
        return '\n'.join(lines)


    def _activate_model(self, sport: str, model_version: str, requested_by: str) -> str:
        sport = (sport or '').lower().strip()
        model_version = (model_version or '').strip()
        allowed = ('football', 'nba', 'nfl', 'euroleague', 'tennis')
        if sport not in allowed:
            return 'Ungültiger Sport für /activate_model. Erlaubt: football, nba, nfl, euroleague, tennis'
        if not model_version:
            return 'Bitte nutze /activate_model <sport> <version>'
        registry = ModelRegistry()
        active_before = registry.get_active(sport)
        activated = registry.set_active(sport, model_version, reason=f'telegram:{requested_by}')
        if not activated:
            candidates = registry.registry.get('candidates', {}).get(sport, [])
            if not candidates:
                return f'Keine Kandidaten für {sport} im Registry gefunden.'
            available = ', '.join(sorted(c.get('model_version', '?') for c in candidates[-10:]))
            return (
                f'Modell {model_version} für {sport} nicht gefunden.\n'
                f'Verfügbare Kandidaten: {available}'
            )
        previous = active_before.get('model_version') if active_before else 'keines'
        metrics = activated.get('metrics') or {}
        metric_bits = []
        if 'roi_percent' in metrics:
            metric_bits.append(f"roi={self._safe_float(metrics.get('roi_percent')):+.2f}%")
        if 'total_profit' in metrics:
            metric_bits.append(f"profit={self._safe_float(metrics.get('total_profit')):+.2f}")
        if 'win_rate' in metrics:
            metric_bits.append(f"wr={self._safe_float(metrics.get('win_rate')):.2f}%")
        metric_text = '\nMetriken: ' + '; '.join(metric_bits) if metric_bits else ''
        return (
            f'Aktives Modell für {sport} umgestellt.\n'
            f'Vorher: {previous}\n'
            f'Jetzt: {activated.get("model_version", "n/a")}{metric_text}'
        )

    def _pipeline_command(self, requested_by: str, pipeline_name: str, continue_on_error: bool = False) -> str:
        pipeline_name = (pipeline_name or '').lower().strip()
        try:
            from shared.pipeline_presets import PIPELINE_PRESETS as _PIPELINE_PRESETS
        except Exception:
            from .pipeline_presets import PIPELINE_PRESETS as _PIPELINE_PRESETS
        if not pipeline_name:
            return 'Bitte nutze /pipeline <name>. Verfügbar: ' + ', '.join(sorted(_PIPELINE_PRESETS.keys()))
        if pipeline_name not in _PIPELINE_PRESETS:
            return 'Unbekannte Pipeline. Verfügbar: ' + ', '.join(sorted(_PIPELINE_PRESETS.keys()))
        cmd = [sys.executable, '-m', 'shared.pipeline_runner', pipeline_name]
        if continue_on_error:
            cmd.append('--continue-on-error')
        return self._start_job(f'pipeline-{pipeline_name}', cmd, requested_by)

    def _stop_job(self, requested_by: str) -> str:
        if not self._job_running() or not self.current_job:
            self.current_job = None
            self.current_process = None
            self._save_current_job()
            return 'Kein laufender Job zum Stoppen.'
        pid = self.current_job.process_pid
        try:
            if self.current_process is not None and self.current_process.poll() is None:
                self.current_process.terminate()
                try:
                    self.current_process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.current_process.kill()
                    self.current_process.wait(timeout=5)
            elif pid and self._pid_running(pid):
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                if self._pid_running(pid):
                    os.kill(pid, signal.SIGKILL)
            self.current_job.status = 'stopped'
            self.current_job.finished_at = now_iso()
            self.current_job.returncode = -15
            self._append_job_history(asdict(self.current_job))
            log_rel = Path(self.current_job.log_path).relative_to(self.root)
            self.current_process = None
            self.current_job = None
            self._save_current_job()
            return f"Job gestoppt von {requested_by}.\nLog: {log_rel}"
        except Exception as exc:
            return f"Stop fehlgeschlagen: {exc}"

    def _job_running(self) -> bool:
        if not self.current_job:
            return False
        if self.current_process is not None:
            return self.current_process.poll() is None
        pid = self.current_job.process_pid
        return bool(pid and self._pid_running(pid))

    def poll_job_completion(self):
        if not self.current_job or self.current_process is None:
            return
        rc = self.current_process.poll()
        if rc is None:
            started = self.current_job.started_at or self.current_job.requested_at
            try:
                started_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                runtime_min = (datetime.now(timezone.utc) - started_dt.astimezone(timezone.utc)).total_seconds() / 60
                if runtime_min > self.max_runtime_minutes:
                    self.current_process.kill()
                    rc = self.current_process.wait(timeout=5)
                    self.current_job.status = 'killed_timeout'
            except Exception:
                pass
            if rc is None:
                return
        self.current_job.returncode = rc
        self.current_job.finished_at = now_iso()
        if self.current_job.status not in ('killed_timeout',):
            self.current_job.status = 'success' if rc == 0 else 'failed'
        self._save_current_job()
        log_tail = self._tail(Path(self.current_job.log_path), 2500)
        summary = (
            f"Job beendet: {self.current_job.name}\n"
            f"Status: {self.current_job.status}\n"
            f"RC: {self.current_job.returncode}\n"
            f"Angefordert von: {self.current_job.requested_by}\n\n"
            f"Log-Auszug:\n{log_tail}"
        )
        self._reply(summary)
        self._append_job_history(asdict(self.current_job))
        self.current_process = None
        self.current_job = None
        self._save_current_job()

    def _start_job(self, name: str, command: List[str], requested_by: str) -> str:
        if self._job_running():
            assert self.current_job is not None
            return f"Schon aktiv: {self.current_job.name}. Bitte erst /status prüfen."
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        log_path = self.log_dir / f'{stamp}-{name}.log'
        with log_path.open('w', encoding='utf-8') as handle:
            handle.write(f"$ {' '.join(command)}\n\n")
            handle.flush()
            proc = subprocess.Popen(
                command,
                cwd=self.root,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
        self.current_process = proc
        self.current_job = JobState(
            name=name,
            command=command,
            requested_by=requested_by,
            requested_at=now_iso(),
            log_path=str(log_path),
            process_pid=proc.pid,
            started_at=now_iso(),
        )
        self._save_current_job()
        return f"Gestartet: {name}\nPID: {proc.pid}\nLog: {log_path.relative_to(self.root)}"

    def build_status(self) -> str:
        tracker = UniversalBetTracker()
        registry = ModelRegistry()
        active = tracker.get_active_bets()
        settled_7 = tracker.get_settled_bets(days=7)
        by_sport: Dict[str, int] = {}
        for row in active:
            sport = row.get('sport', 'unknown')
            by_sport[sport] = by_sport.get(sport, 0) + 1
        perf = tracker.calculate_performance(days=30, sport=None)
        sport_breakdown = ', '.join(f'{k}:{v}' for k, v in sorted(by_sport.items())) or 'keine'
        parts = [
            'OpenClaw Control Status',
            f'Zeit: {now_iso()}',
            f'Aktive Bets: {len(active)} ({sport_breakdown})',
            f'Settled 7d: {len(settled_7)}',
            f"ROI 30d: {perf.get('roi_percent', 0):+.2f}% | Profit: {perf.get('total_profit', 0):+.2f}",
        ]
        active_models = registry.registry.get('active', {})
        if active_models:
            model_text = ', '.join(f"{sport}:{info.get('model_version', 'n/a')}" for sport, info in sorted(active_models.items()))
            parts.append(f'Aktive Modelle: {model_text}')
        if self._job_running() and self.current_job:
            parts.append(f'Laufender Job: {self.current_job.name} seit {self.current_job.started_at}')
            parts.append(f"Log: {Path(self.current_job.log_path).relative_to(self.root)}")
        else:
            parts.append('Laufender Job: keiner')
        pipeline_dir = data_root() / 'pipeline_runs'
        latest = sorted(pipeline_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:2]
        if latest:
            rows = []
            for path in latest:
                try:
                    payload = json.loads(path.read_text(encoding='utf-8'))
                    rows.append(f"{payload.get('pipeline')}: {'OK' if payload.get('success') else 'FAIL'} @ {payload.get('timestamp')}")
                except Exception:
                    rows.append(f'{path.stem}: unreadable')
            parts.append('Letzte Pipelines: ' + ' | '.join(rows))
        return '\n'.join(parts)

    def _report_command(self, requested_by: str, sport: str, days: int) -> str:
        sport = sport.lower()
        if sport not in ('all', 'football', 'nba', 'nfl', 'euroleague', 'tennis'):
            return 'Ungültiger Sport für /report. Erlaubt: all, football, nba, nfl, euroleague, tennis'
        days = max(1, min(days, 365))
        cmd = [sys.executable, '-m', 'shared.feedback_loop', '--sport', sport, '--days', str(days), '--generate-dashboard']
        return self._start_job(f'report-{sport}-{days}d', cmd, requested_by)

    def _build_command(self, cmd: str, args: List[str], requested_by: str) -> str:
        py = sys.executable
        if cmd == '/pipeline':
            pipeline_name = args[0] if args else ''
            continue_on_error = any(str(arg).lower() in ('--continue-on-error', 'continue', 'coe') for arg in args[1:])
            return self._pipeline_command(requested_by, pipeline_name, continue_on_error=continue_on_error)
        if cmd in ('/daily', '/weekly', '/uefa', '/props', '/full'):
            name = cmd.lstrip('/')
            return self._pipeline_command(requested_by, name)
        if cmd == '/settleteam':
            sport = args[0].lower() if args else 'football'
            if sport not in ('football', 'nba', 'nfl', 'euroleague', 'tennis'):
                return 'Ungültiger Sport für /settleteam.'
            return self._start_job(f'settleteam-{sport}', [py, 'shared/settle_team_bets.py', '--sport', sport], requested_by)
        if cmd == '/settleprops':
            sport = args[0].lower() if args else 'all'
            if sport not in ('all', 'football', 'nba', 'nfl'):
                return 'Ungültiger Sport für /settleprops.'
            return self._start_job(f'settleprops-{sport}', [py, 'shared/settle_player_props.py', '--sport', sport], requested_by)
        if cmd == '/report':
            sport = args[0] if args else 'all'
            days = int(args[1]) if len(args) > 1 and str(args[1]).isdigit() else 30
            return self._report_command(requested_by, sport, days)
        if cmd == '/dashboard':
            dash = data_root() / 'monitoring' / 'dashboard.html'
            if dash.exists():
                changed = datetime.fromtimestamp(dash.stat().st_mtime).isoformat(timespec='seconds')
                return f'Dashboard vorhanden: {dash.relative_to(self.root)}\nZuletzt geändert: {changed}'
            return 'Noch kein Dashboard erzeugt. Nutze /report all 30 oder /daily.'
        if cmd == '/tail':
            if self.current_job:
                return self._tail(Path(self.current_job.log_path))
            return 'Kein aktiver Job. Nutze /status.'
        if cmd == '/stop':
            return self._stop_job(requested_by)
        if cmd == '/lastbets':
            limit = int(args[0]) if args and str(args[0]).isdigit() else 5
            return self._latest_bets_summary(limit=max(1, min(limit, 10)))
        if cmd == '/performance':
            sport = args[0] if args else 'all'
            days = int(args[1]) if len(args) > 1 and str(args[1]).isdigit() else 30
            return self._performance_summary(sport=sport, days=days)
        if cmd == '/jobs':
            limit = int(args[0]) if args and str(args[0]).isdigit() else 5
            return self._jobs_summary(limit=limit)
        if cmd == '/history':
            limit = int(args[0]) if args and str(args[0]).isdigit() else 5
            return self._history_summary(limit=limit)
        if cmd == '/models':
            sport = args[0] if args else 'all'
            return self._models_summary(sport=sport)
        if cmd == '/activate_model':
            sport = args[0] if args else ''
            model_version = args[1] if len(args) > 1 else ''
            return self._activate_model(sport, model_version, requested_by)
        if cmd == '/status':
            return self.build_status()
        if cmd == '/ping':
            return 'pong'
        if cmd in ('/help', '/start'):
            return (
                'OpenClaw Telegram Control\n\n'
                '/status – Systemstatus und letzter Pipeline-Stand\n'
                '/daily – tägliche Gesamtpipeline\n'
                '/weekly – Wochenlauf mit Retrain/Gate\n'
                '/uefa – UCL/UEL/UECL Lauf + Settlement + Props\n'
                '/props – Props-Live + Props-Settlement\n'
                '/full – daily + weekly\n'
                '/pipeline <name> – startet ein Pipeline-Preset, z. B. /pipeline daily\n'
                '/settleteam <sport> – football|nba|nfl|euroleague|tennis\n'
                '/settleprops <sport> – football|nba|nfl|all\n'
                '/report <sport> <days> – Report + Dashboard, z. B. /report all 30\n'
                '/performance [sport] [days] – Kurzperformance, z. B. /performance football 30\n'
                '/jobs [n] – aktiver Job + letzte Läufe\n'
                '/history [n] – letzte Pipelines + Modell-Aktivierungen\n'
                '/models [sport] – aktive und neueste Kandidatenmodelle\n'
                '/activate_model <sport> <version> – Kandidat aktiv setzen\n'
                '/lastbets [n] – letzte aktiven + settled Bets, max 10\n'
                '/stop – laufenden Job sauber stoppen\n'
                '/dashboard – Dashboard-Pfad lokal anzeigen\n'
                '/tail – aktuellen Job-Logauszug senden\n'
                '/ping – Bot-Test'
            )
        return 'Unbekannter Befehl. Nutze /help.'

    def handle_update(self, update: Dict):
        msg = update.get('message') or update.get('edited_message') or {}
        text = (msg.get('text') or '').strip()
        if not text.startswith('/'):
            return
        if not self._authorized(msg):
            return
        requested_by = self._display_user(msg)
        parts = text.split()
        cmd = parts[0].split('@')[0].lower()
        args = parts[1:]
        try:
            reply = self._build_command(cmd, args, requested_by)
        except Exception as exc:
            reply = f'Fehler bei {cmd}: {exc}'
        self._reply(reply)

    def poll_once(self):
        offset = self.get_offset()
        try:
            payload = self.api_request('getUpdates', {'timeout': 30, 'offset': offset + 1})
        except URLError:
            return
        except Exception:
            return
        for item in payload.get('result', []):
            self.handle_update(item)
            self.save_offset(int(item.get('update_id', 0)))

    def run_forever(self):
        if not self.enabled:
            raise SystemExit('Telegram control bot is not enabled. Check TELEGRAM_* env settings.')
        self._reply('OpenClaw Telegram Control ist aktiv. Nutze /help für Befehle.')
        while True:
            self.poll_job_completion()
            self.poll_once()
            time.sleep(self.poll_interval)


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description='Run the OpenClaw Telegram control bot')
    parser.add_argument('--once', action='store_true', help='Process updates once and exit')
    parser.add_argument('--status', action='store_true', help='Print a local status summary and exit')
    args = parser.parse_args(argv)

    bot = TelegramControlBot()
    if args.status:
        print(bot.build_status())
        return
    if args.once:
        if not bot.enabled:
            raise SystemExit('Telegram control bot is not enabled. Check TELEGRAM_* env settings.')
        bot.poll_job_completion()
        bot.poll_once()
        return
    bot.run_forever()


if __name__ == '__main__':
    main()

"""Generate a lightweight HTML dashboard from tracked bets and registry metadata."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, Optional

from .runtime_utils import data_root, ensure_parent, now_iso


def _metric_card(title: str, value: str, sub: str = '') -> str:
    return f"<div class='card'><h3>{html.escape(title)}</h3><div class='value'>{html.escape(str(value))}</div><div class='sub'>{html.escape(sub)}</div></div>"


class DashboardBuilder:
    def __init__(self, out_path: Optional[Path] = None):
        self.out_path = out_path or data_root() / 'monitoring' / 'dashboard.html'

    def build(self, performance: Dict, registry: Optional[Dict] = None,
              calibration: Optional[Dict] = None) -> Path:
        cards = [
            _metric_card('Bets', performance.get('total_bets', 0), f"Wins {performance.get('wins', 0)} / Losses {performance.get('losses', 0)}"),
            _metric_card('ROI', f"{performance.get('roi_percent', 0):+.2f}%", f"Profit {performance.get('total_profit', 0):+.2f}"),
            _metric_card('Win rate', f"{performance.get('win_rate', 0):.2f}%", performance.get('sport', 'all')),
            _metric_card('CLV', f"{performance.get('clv', {}).get('avg_clv_percent', 0):+.2f}%", performance.get('clv', {}).get('interpretation', 'n/a')),
            _metric_card('Max drawdown', f"{performance.get('max_drawdown_percent', 0):+.2f}%", 'settled bets window'),
        ]
        active_models = ''
        if registry:
            active = registry.get('active', {})
            items = ''.join(f"<li><strong>{html.escape(sport)}</strong>: {html.escape(info.get('model_version', 'n/a'))}</li>" for sport, info in active.items()) or '<li>none</li>'
            active_models = f"<div class='panel'><h2>Active models</h2><ul>{items}</ul></div>"
        calibration_html = ''
        if calibration:
            rows = []
            for key, info in sorted(calibration.get('markets', {}).items()):
                rows.append(f"<tr><td>{html.escape(key)}</td><td>{info.get('sample_size', 0)}</td><td>{info.get('calibration_gap', 0):+.3f}</td><td>{info.get('stake_multiplier', 1.0):.2f}</td></tr>")
            table = ''.join(rows) or '<tr><td colspan="4">No calibration data yet</td></tr>'
            calibration_html = f"<div class='panel'><h2>Market calibration</h2><table><tr><th>Market</th><th>Samples</th><th>Gap</th><th>Stake x</th></tr>{table}</table></div>"
        market_rows = ''.join(
            f"<tr><td>{html.escape(m)}</td><td>{stats.get('bets', 0)}</td><td>{stats.get('win_rate', 0):.1f}%</td><td>{stats.get('profit', 0):+.2f}</td></tr>"
            for m, stats in sorted(performance.get('market_performance', {}).items())
        ) or '<tr><td colspan="4">No market data</td></tr>'
        league_rows = ''.join(
            f"<tr><td>{html.escape(l)}</td><td>{stats.get('bets', 0)}</td><td>{stats.get('roi_percent', 0):+.1f}%</td><td>{stats.get('profit', 0):+.2f}</td></tr>"
            for l, stats in sorted(performance.get('league_performance', {}).items())
        ) or '<tr><td colspan="4">No league data</td></tr>'
        html_doc = f"""
        <!doctype html>
        <html>
        <head>
          <meta charset='utf-8'>
          <title>Betting Algorithm V6 Dashboard</title>
          <style>
            body {{ font-family: Arial, sans-serif; margin: 24px; background: #f7f8fa; color: #1f2937; }}
            h1, h2 {{ margin-bottom: 10px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }}
            .card, .panel {{ background: white; border-radius: 16px; padding: 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
            .value {{ font-size: 28px; font-weight: 700; margin: 6px 0; }}
            .sub {{ color: #6b7280; font-size: 13px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
            ul {{ margin: 0; padding-left: 20px; }}
          </style>
        </head>
        <body>
          <h1>Betting Algorithm V6 Dashboard</h1>
          <div class='sub'>Generated {html.escape(now_iso())}</div>
          <div class='grid'>{''.join(cards)}</div>
          <div class='panel'><h2>Market performance</h2><table><tr><th>Market</th><th>Bets</th><th>Win rate</th><th>Profit</th></tr>{market_rows}</table></div>
          <div class='panel'><h2>League performance</h2><table><tr><th>League</th><th>Bets</th><th>ROI</th><th>Profit</th></tr>{league_rows}</table></div>
          {active_models}
          {calibration_html}
        </body>
        </html>
        """
        ensure_parent(self.out_path)
        self.out_path.write_text(html_doc, encoding='utf-8')
        return self.out_path

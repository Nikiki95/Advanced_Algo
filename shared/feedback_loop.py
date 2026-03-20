"""Universal tracker, reporting, calibration, and feedback tooling for V6."""
from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .calibration import MarketCalibration
from .monitoring_dashboard import DashboardBuilder
from .model_registry import ModelRegistry
from .runtime_utils import data_root, ensure_parent, json_default, now_iso
from .walkforward import WalkForwardOptimizer


@dataclass
class TrackedBet:
    bet_id: str
    timestamp: str
    execution_mode: str
    sport: str
    league: str
    match_id: str
    event_id: str
    home_team: str
    away_team: str
    match_date: str
    bet_type: str
    market: str
    selection: str
    line: Optional[float]
    odds: float
    opening_odds: float
    bookmaker: str
    bookmaker_options: List[Dict]
    model_prob: float
    market_prob: float
    value_percentage: float
    expected_value: float
    raw_kelly_stake: float
    kelly_stake: float
    confidence: str
    risk_status: str
    risk_reasons: List[str]
    stake_multiplier: float
    model_version: str
    feature_set_version: str
    data_version: str
    thresholds_version: str
    calibration_version: str
    odds_timestamp: Optional[str] = None
    player_name: Optional[str] = None
    prop_side: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    closing_odds: Optional[float] = None
    closing_bookmaker: Optional[str] = None
    clv: Optional[float] = None
    actual_result: Optional[str] = None
    profit_loss: Optional[float] = None
    settled: bool = False
    settled_at: Optional[str] = None


class UniversalBetTracker:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or data_root() / "tracked_bets"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.active_file = self.data_dir / "active_bets.jsonl"
        self.settled_file = self.data_dir / "settled_bets.jsonl"
        self.performance_file = self.data_dir / "performance.json"

    def place_bet(self, bet_data: Dict, sport: str) -> str:
        bet_id = str(uuid.uuid4())[:8]
        opening_odds = float(bet_data.get("opening_odds") or bet_data.get("odds") or 0)
        odds = float(bet_data.get("odds") or opening_odds or 0)
        market_prob = float(bet_data.get("market_prob") or (1.0 / odds if odds > 1 else 0.0))
        model_prob = float(bet_data.get("model_prob") or 0.0)
        expected_value = float(
            bet_data.get("expected_value") or (model_prob * odds - 1.0 if odds > 1 else 0.0)
        )
        raw_stake = float(bet_data.get("raw_kelly_stake") or bet_data.get("kelly_stake") or 0.0)
        adj_stake = float(bet_data.get("kelly_stake") or raw_stake)
        tracked = TrackedBet(
            bet_id=bet_id,
            timestamp=bet_data.get("timestamp") or now_iso(),
            execution_mode=bet_data.get("execution_mode", "live"),
            sport=sport,
            league=bet_data.get("league", ""),
            match_id=bet_data.get("match_id", ""),
            event_id=bet_data.get("event_id", ""),
            home_team=bet_data.get("home_team", ""),
            away_team=bet_data.get("away_team", ""),
            match_date=bet_data.get("match_date", ""),
            bet_type=bet_data.get("bet_type", ""),
            market=bet_data.get("market", bet_data.get("bet_type", "unknown")),
            selection=bet_data.get("selection", ""),
            line=bet_data.get("line"),
            odds=odds,
            opening_odds=opening_odds,
            bookmaker=bet_data.get("bookmaker", ""),
            bookmaker_options=bet_data.get("bookmaker_options", []),
            model_prob=model_prob,
            market_prob=market_prob,
            value_percentage=float(bet_data.get("value_percentage", 0.0)),
            expected_value=expected_value,
            raw_kelly_stake=raw_stake,
            kelly_stake=adj_stake,
            confidence=bet_data.get("confidence", "low"),
            risk_status=bet_data.get("risk_status", "approved"),
            risk_reasons=bet_data.get("risk_reasons", []),
            stake_multiplier=float(bet_data.get("stake_multiplier", 1.0)),
            model_version=bet_data.get("model_version", "unversioned"),
            feature_set_version=bet_data.get("feature_set_version", "v3"),
            data_version=bet_data.get("data_version", "v3"),
            thresholds_version=bet_data.get("thresholds_version", "v3"),
            calibration_version=bet_data.get("calibration_version", "v3"),
            odds_timestamp=bet_data.get("odds_timestamp"),
            player_name=bet_data.get("player_name"),
            prop_side=bet_data.get("prop_side"),
            metadata=bet_data.get("metadata", {}),
            closing_odds=bet_data.get("closing_odds"),
            closing_bookmaker=bet_data.get("closing_bookmaker"),
            clv=bet_data.get("clv"),
        )
        with self.active_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(tracked), default=json_default) + "\n")
        return bet_id

    def settle_bet(
        self,
        bet_id: str,
        result: str,
        profit_loss: float,
        closing_odds: Optional[float] = None,
        closing_bookmaker: Optional[str] = None,
        settlement_details: Optional[Dict] = None,
    ) -> bool:
        active = self._load_jsonl(self.active_file)
        target = None
        remaining = []
        for row in active:
            if row.get("bet_id") == bet_id:
                target = row
            else:
                remaining.append(row)
        if not target:
            return False
        target["actual_result"] = result
        target["profit_loss"] = float(profit_loss)
        target["settled"] = True
        target["settled_at"] = now_iso()
        if closing_odds:
            target["closing_odds"] = float(closing_odds)
            target["closing_bookmaker"] = closing_bookmaker
            opening = float(target.get("opening_odds") or target.get("odds") or 0)
            if opening > 1 and closing_odds > 1:
                opening_imp = 1.0 / opening
                closing_imp = 1.0 / float(closing_odds)
                target["clv"] = (closing_imp - opening_imp) / opening_imp
        if settlement_details:
            metadata = target.get("metadata") if isinstance(target.get("metadata"), dict) else {}
            metadata.update(settlement_details)
            target["metadata"] = metadata
        self._write_jsonl(self.active_file, remaining)
        with self.settled_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(target, default=json_default) + "\n")
        return True

    def get_active_bets(self, sport: Optional[str] = None, execution_mode: Optional[str] = None) -> List[Dict]:
        rows = self._load_jsonl(self.active_file)
        if sport:
            rows = [r for r in rows if r.get("sport") == sport]
        if execution_mode:
            rows = [r for r in rows if r.get("execution_mode") == execution_mode]
        return rows

    def get_settled_bets(
        self,
        days: int = 30,
        sport: Optional[str] = None,
        execution_mode: Optional[str] = None,
    ) -> List[Dict]:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        rows = []
        for row in self._load_jsonl(self.settled_file):
            try:
                ts = datetime.fromisoformat(str(row.get("timestamp")).replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except Exception:
                continue
            if ts < cutoff:
                continue
            if sport and row.get("sport") != sport:
                continue
            if execution_mode and row.get("execution_mode") != execution_mode:
                continue
            rows.append(row)
        return rows

    def calculate_performance(
        self,
        days: int = 30,
        sport: Optional[str] = None,
        execution_mode: Optional[str] = None,
    ) -> Dict:
        bets = self.get_settled_bets(days=days, sport=sport, execution_mode=execution_mode)
        perf = self._calculate_performance_from_bets(
            bets,
            days=days,
            sport=sport or "all",
            execution_mode=execution_mode or "all",
        )
        self.performance_file.write_text(json.dumps(perf, indent=2), encoding="utf-8")
        return perf

    def _calculate_performance_from_bets(
        self, bets: List[Dict], days: int, sport: str, execution_mode: str
    ) -> Dict:
        if not bets:
            return {
                "period_days": days,
                "sport": sport,
                "execution_mode": execution_mode,
                "total_bets": 0,
                "wins": 0,
                "losses": 0,
                "voids": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "total_staked": 0.0,
                "roi_percent": 0.0,
                "avg_value_percent": 0.0,
                "market_performance": {},
                "league_performance": {},
                "clv": {"available": False},
                "max_drawdown_percent": 0.0,
                "updated_at": now_iso(),
            }
        wins = sum(1 for b in bets if b.get("actual_result") == "win")
        losses = sum(1 for b in bets if b.get("actual_result") == "loss")
        voids = sum(1 for b in bets if b.get("actual_result") in ("void", "push"))
        total_profit = sum(float(b.get("profit_loss") or 0) for b in bets)
        total_staked = sum(float(b.get("kelly_stake") or 0) for b in bets if float(b.get("kelly_stake") or 0) > 0)
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) else 0.0
        roi = (total_profit / total_staked * 100) if total_staked else 0.0
        avg_value = (sum(float(b.get("value_percentage") or 0) for b in bets) / len(bets)) * 100

        market_perf = {}
        for market in sorted(set(b.get("market", "unknown") for b in bets)):
            subset = [b for b in bets if b.get("market") == market]
            graded = [b for b in subset if b.get("actual_result") in ("win", "loss")]
            mw = sum(1 for b in graded if b.get("actual_result") == "win")
            market_perf[market] = {
                "bets": len(subset),
                "win_rate": round(mw / len(graded) * 100, 2) if graded else 0.0,
                "profit": round(sum(float(b.get("profit_loss") or 0) for b in subset), 2),
            }

        league_perf = {}
        for league in sorted(set(b.get("league", "unknown") for b in bets)):
            subset = [b for b in bets if b.get("league") == league]
            staked = sum(float(b.get("kelly_stake") or 0) for b in subset)
            profit = sum(float(b.get("profit_loss") or 0) for b in subset)
            league_perf[league] = {
                "bets": len(subset),
                "profit": round(profit, 2),
                "roi_percent": round((profit / staked * 100) if staked else 0.0, 2),
            }

        drawdown = self._max_drawdown_percent(bets)
        clv_values = [float(b["clv"]) for b in bets if b.get("clv") is not None]
        clv = {"available": False}
        if clv_values:
            avg_clv = sum(clv_values) / len(clv_values)
            positive_rate = sum(1 for c in clv_values if c > 0) / len(clv_values) * 100
            clv = {
                "available": True,
                "tracked": len(clv_values),
                "avg_clv_percent": round(avg_clv * 100, 2),
                "positive_clv_rate": round(positive_rate, 2),
                "interpretation": "GOOD" if avg_clv > 0.01 else "NEUTRAL" if avg_clv > -0.01 else "CONCERNING",
            }
        return {
            "period_days": days,
            "sport": sport,
            "execution_mode": execution_mode,
            "total_bets": len(bets),
            "wins": wins,
            "losses": losses,
            "voids": voids,
            "win_rate": round(win_rate, 2),
            "total_profit": round(total_profit, 2),
            "total_staked": round(total_staked, 2),
            "roi_percent": round(roi, 2),
            "avg_value_percent": round(avg_value, 2),
            "market_performance": market_perf,
            "league_performance": league_perf,
            "clv": clv,
            "max_drawdown_percent": round(drawdown, 2),
            "updated_at": now_iso(),
        }

    def _max_drawdown_percent(self, bets: List[Dict]) -> float:
        ordered = sorted(bets, key=lambda x: x.get("timestamp", ""))
        equity = 0.0
        peak = 0.0
        min_dd = 0.0
        for row in ordered:
            equity += float(row.get("profit_loss") or 0)
            peak = max(peak, equity)
            dd = equity - peak
            min_dd = min(min_dd, dd)
        stake = sum(float(b.get("kelly_stake") or 0) for b in ordered)
        return (min_dd / stake * 100) if stake else 0.0

    def _load_jsonl(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _write_jsonl(self, path: Path, rows: List[Dict]):
        ensure_parent(path)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, default=json_default) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Betting Algorithm V6 feedback loop")
    parser.add_argument("--sport", choices=["football", "nba", "nfl", "euroleague", "tennis", "all"], default="all")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--generate-calibration", action="store_true")
    parser.add_argument("--generate-dashboard", action="store_true")
    parser.add_argument("--optimize-thresholds", action="store_true")
    args = parser.parse_args()

    tracker = UniversalBetTracker()
    sport = None if args.sport == "all" else args.sport
    perf = tracker.calculate_performance(days=args.days, sport=sport)
    print(json.dumps(perf, indent=2))

    settled = tracker.get_settled_bets(days=args.days, sport=sport)
    calibration_profile = None
    if args.generate_calibration or not args.report_only:
        calibration_profile = MarketCalibration().generate(settled)
        print(f"Calibration markets: {len(calibration_profile.get('markets', {}))}")
    if args.optimize_thresholds:
        summary = WalkForwardOptimizer().optimize_thresholds(settled, sport=sport)
        print(f"Best threshold: {summary.get('best')}")
    if args.generate_dashboard or not args.report_only:
        registry = ModelRegistry().registry
        dashboard = DashboardBuilder().build(
            perf,
            registry=registry,
            calibration=calibration_profile or MarketCalibration().profile,
        )
        print(f"Dashboard: {dashboard}")


if __name__ == "__main__":
    main()

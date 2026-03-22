#!/usr/bin/env python3
"""Football live runner V3 with versioning, risk controls, calibration, and CLV snapshots."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from shared.calibration import MarketCalibration
from shared.closing_line import ClosingLineManager
from shared.feedback_loop import UniversalBetTracker
from shared.model_registry import ModelRegistry
from shared.risk_manager import PortfolioRiskManager
from shared.runtime_utils import canonical_event_key, load_env, now_iso
from config import config
from engine.value_engine import ValueBet, ValueEngine
from model.dixon_coles import DixonColesModel
from notifications.telegram import TelegramNotifier
from scraper.theoddsapi import TheOddsAPIClient

load_env()

LEAGUE_KEY_MAP = {
    "D1": "soccer_germany_bundesliga",
    "D2": "soccer_germany_bundesliga2",  # Korrekter Key
    "E0": "soccer_epl",
    "E1": "soccer_efl_champ",  # Championship (korrekter Key)
    "SP1": "soccer_spain_la_liga",
    "I1": "soccer_italy_serie_a",
    "F1": "soccer_france_ligue_one",
    "P1": "soccer_portugal_primeira_liga",
    "N1": "soccer_netherlands_eredivisie",
}

SUPPORTED_LEAGUES = list(LEAGUE_KEY_MAP.keys())


class LiveCronRunner:
    def __init__(self, execution_mode: str = "live"):
        self.execution_mode = execution_mode
        self.api_client = TheOddsAPIClient()
        self.notifier = TelegramNotifier()
        self.tracker = UniversalBetTracker()
        self.calibration = MarketCalibration()
        self.closing = ClosingLineManager()
        self.registry = ModelRegistry()
        self.risk = PortfolioRiskManager(bankroll=float(getattr(config, "DEFAULT_BANKROLL", 1000.0)))
        self.models_dir = Path("football/models/leagues") if Path("football/models/leagues").exists() else Path("models/leagues")
        self.results_dir = Path("football/data/results") if Path("football/data").exists() else Path("data/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.model = None
        self.model_path = None

    def _load_league_model(self, league_code: str) -> bool:
        model_path = self.models_dir / f"dixon_coles_{league_code}.pkl"
        if not model_path.exists():
            return False
        self.model = DixonColesModel.load(model_path)
        self.model_path = model_path
        self.registry.ensure_registered_from_file(f"football_{league_code}", model_path)
        return True

    def _market_meta(self, bet: ValueBet) -> Dict:
        line = None
        if str(bet.bet_type).startswith("Over_") or str(bet.bet_type).startswith("Under_"):
            market = "totals"
            try:
                line = float(str(bet.bet_type).split("_", 1)[1])
            except Exception:
                line = 2.5
        elif bet.bet_type in ("1X", "X2", "12"):
            market = "dc"
        else:
            market = "1x2"
        return {"market": market, "line": line}

    def _record_snapshots(self, odds_match):
        rows = []
        for bookmaker, odds in odds_match.odds_1.items():
            rows.append({"market": "1x2", "selection": odds_match.home_team, "bookmaker": bookmaker, "odds": odds})
        for bookmaker, odds in odds_match.odds_x.items():
            rows.append({"market": "1x2", "selection": "Draw", "bookmaker": bookmaker, "odds": odds})
        for bookmaker, odds in odds_match.odds_2.items():
            rows.append({"market": "1x2", "selection": odds_match.away_team, "bookmaker": bookmaker, "odds": odds})
        for bookmaker, odds in odds_match.odds_over.items():
            rows.append({"market": "totals", "selection": f"Over {odds_match.ou_line}", "bookmaker": bookmaker, "odds": odds, "line": odds_match.ou_line})
        for bookmaker, odds in odds_match.odds_under.items():
            rows.append({"market": "totals", "selection": f"Under {odds_match.ou_line}", "bookmaker": bookmaker, "odds": odds, "line": odds_match.ou_line})
        self.closing.record_candidates(
            "football",
            odds_match.home_team,
            odds_match.away_team,
            odds_match.commence_time.isoformat(),
            odds_match.event_id,
            rows,
        )

    def _normalize_team_name(self, name: str, league_code: str = "") -> str:
        """Map API team names to model team names."""
        # Common normalizations
        name = name.strip()
        
        # Bundesliga (D1, D2)
        bundesliga_map = {
            "FSV Mainz 05": "Mainz",
            "1. FSV Mainz 05": "Mainz",
            "Eintracht Frankfurt": "Ein Frankfurt",
            "Eintracht Frankfurt ": "Frankfurt",
            "Borussia Dortmund": "Dortmund",
            "Borussia Mönchengladbach": "Mgladbach",
            "Borussia Monchengladbach": "Mgladbach",
            "VfB Stuttgart": "Stuttgart",
            "VfL Wolfsburg": "Wolfsburg",
            "TSG 1899 Hoffenheim": "Hoffenheim",
            "TSG Hoffenheim": "Hoffenheim",
            "SC Freiburg": "Freiburg",
            "Sport-Club Freiburg": "Freiburg",
            "FC Augsburg": "Augsburg",
            "Hertha BSC": "Hertha",
            "Hertha Berlin": "Hertha",
            "1. FC Köln": "Koln",
            "1. FC Union Berlin": "Union Berlin",
            "Werder Bremen": "Werder",
            "SV Werder Bremen": "Werder",
            "FC St. Pauli": "St. Pauli",
            "Holstein Kiel": "Kiel",
            "VfL Bochum": "Bochum",
            "FC Heidenheim": "Heidenheim",
            "1. FC Heidenheim": "Heidenheim",
        }
        
        # Premier League (E0)
        epl_map = {
            "Manchester City": "Man City",
            "Manchester United": "Man United",
            "Newcastle United": "Newcastle",
            "Tottenham Hotspur": "Tottenham",
            "West Ham United": "West Ham",
            "Brighton and Hove Albion": "Brighton",
            "Wolverhampton Wanderers": "Wolves",
            "Nottingham Forest": "Nott'm Forest",
            "Leicester City": "Leicester",
            "Ipswich Town": "Ipswich",
            "Southampton": "Southampton",
        }
        
        # La Liga (SP1)
        laliga_map = {
            "Atlético Madrid": "Ath Madrid",
            "Athletic Club": "Ath Bilbao",
            "Real Betis": "Betis",
            "Celta de Vigo": "Celta",
            "RC Celta de Vigo": "Celta",
            "Deportivo Alavés": "Alaves",
            "Girona FC": "Girona",
            "Rayo Vallecano": "Vallecano",
            "Real Sociedad": "Sociedad",
            "UD Las Palmas": "Las Palmas",
            "RCD Mallorca": "Mallorca",
            "CD Leganés": "Leganes",
            "Real Valladolid": "Valladolid",
            "RCD Espanyol": "Espanyol",
        }
        
        # Serie A (I1)
        seriea_map = {
            "Inter Milan": "Inter",
            "FC Internazionale Milano": "Inter",
            "AC Milan": "Milan",
            "AS Roma": "Roma",
            "SS Lazio": "Lazio",
            "SSC Napoli": "Napoli",
            "Juventus FC": "Juventus",
            "Atalanta BC": "Atalanta",
            "Bologna FC 1909": "Bologna",
            "ACF Fiorentina": "Fiorentina",
            "Torino FC": "Torino",
            "Udinese Calcio": "Udinese",
            "US Lecce": "Lecce",
            "AC Monza": "Monza",
            "Genoa CFC": "Genoa",
            "Cagliari Calcio": "Cagliari",
            "Hellas Verona FC": "Verona",
            "Empoli FC": "Empoli",
            "Como 1907": "Como",
            "Venezia FC": "Venezia",
            "Parma Calcio 1913": "Parma",
        }
        
        # Ligue 1 (F1)
        ligue1_map = {
            "Paris Saint-Germain": "Paris SG",
            "Paris Saint-Germain FC": "Paris SG",
            "AS Monaco": "Monaco",
            "Olympique de Marseille": "Marseille",
            "Olympique Lyonnais": "Lyon",
            "LOSC Lille": "Lille",
            "Stade Rennais FC": "Rennes",
            "OGC Nice": "Nice",
            "RC Lens": "Lens",
            "RC Strasbourg Alsace": "Strasbourg",
            "Montpellier HSC": "Montpellier",
            "FC Nantes": "Nantes",
            "Stade de Reims": "Reims",
            "Stade Brestois 29": "Brest",
            "Toulouse FC": "Toulouse",
            "AJ Auxerre": "Auxerre",
            "Havre AC": "Le Havre",
            "Angers SCO": "Angers",
            "AS Saint-Étienne": "St Etienne",
        }
        
        # Combine all maps
        all_maps = {**bundesliga_map, **epl_map, **laliga_map, **seriea_map, **ligue1_map}
        
        return all_maps.get(name, name)

    def _find_team_in_model(self, name: str) -> str:
        """Find team name in model, trying normalized versions."""
        if not self.model:
            return name
            
        # Direct match
        if name in self.model.team_ratings:
            return name
            
        # Try normalized
        normalized = self._normalize_team_name(name)
        if normalized in self.model.team_ratings:
            return normalized
            
        # Try partial match
        for model_team in self.model.team_ratings.keys():
            if model_team.lower() in name.lower() or name.lower() in model_team.lower():
                return model_team
                
        return normalized  # Return normalized even if not found (will fail gracefully)

    def _analyze_match(self, odds_match) -> List[ValueBet]:
        # Map team names to model names
        home_mapped = self._find_team_in_model(odds_match.home_team)
        away_mapped = self._find_team_in_model(odds_match.away_team)
        
        # Check if teams exist in model
        if home_mapped not in self.model.team_ratings or away_mapped not in self.model.team_ratings:
            return []
            
        pred = self.model.predict(home_mapped, away_mapped)
        if not pred:
            return []
        pred.home_team = odds_match.home_team  # Keep original names for output
        pred.away_team = odds_match.away_team
        pred.league = getattr(odds_match, "league", "")
        hist_perf = self.tracker.calculate_performance(days=90, sport="football", execution_mode=self.execution_mode)
        engine = ValueEngine(historical_performance=hist_perf)
        return engine.analyze_match(pred, odds_match)

    def _dedupe_key(self, bet_payload: Dict) -> tuple:
        return (bet_payload.get("event_id"), bet_payload.get("market"), bet_payload.get("selection"))

    def _track_bet(self, bet: ValueBet, league_code: str, active_cache: List[Dict]) -> Dict | None:
        model_version = self.model_path.stem if self.model_path else f"football-{league_code}"
        market_meta = self._market_meta(bet)
        calibration = self.calibration.adjust_bet("football", market_meta["market"], bet.kelly_stake, bet.value_percentage, bet.confidence)
        payload = {
            "execution_mode": self.execution_mode,
            "league": league_code,
            "match_id": getattr(bet, "match_id", ""),
            "event_id": canonical_event_key("football", bet.home_team, bet.away_team, bet.match_datetime.isoformat()),
            "home_team": bet.home_team,
            "away_team": bet.away_team,
            "match_date": bet.match_datetime.isoformat(),
            "bet_type": bet.bet_type,
            "market": market_meta["market"],
            "selection": bet.selection,
            "line": market_meta["line"],
            "odds": bet.best_odds,
            "opening_odds": bet.best_odds,
            "bookmaker": bet.bookmaker,
            "bookmaker_options": [],
            "model_prob": bet.model_probability,
            "market_prob": bet.market_probability,
            "value_percentage": bet.value_percentage,
            "expected_value": bet.expected_value,
            "raw_kelly_stake": bet.kelly_stake,
            "kelly_stake": calibration["adjusted_stake"],
            "confidence": calibration["adjusted_confidence"],
            "stake_multiplier": calibration["stake_multiplier"],
            "calibration_version": self.calibration.profile.get("version", "v3"),
            "model_version": model_version,
            "feature_set_version": "v3",
            "data_version": "v3",
            "thresholds_version": "v3",
            "odds_timestamp": bet.odds_timestamp or now_iso(),
        }
        if self._dedupe_key(payload) in {self._dedupe_key(b) for b in active_cache}:
            return None
        risk = self.risk.evaluate_bet({"sport": "football", **payload}, active_cache)
        if not risk.approved:
            return None
        payload["risk_status"] = risk.status
        payload["risk_reasons"] = risk.reasons
        payload["kelly_stake"] = risk.approved_stake
        payload["stake_multiplier"] = round(payload["stake_multiplier"] * risk.stake_multiplier, 3)
        payload["sport"] = "football"
        self.tracker.place_bet(payload, sport="football")
        active_cache.append({"sport": "football", **payload})
        return payload

    def check_live_values(self, leagues: List[str], send_alerts: bool = True) -> Dict:
        result = {"timestamp": now_iso(), "execution_mode": self.execution_mode, "leagues_checked": leagues, "bets_tracked": 0, "alerts_sent": 0}
        active_cache = self.tracker.get_active_bets(sport="football")
        alert_bets = []
        for league_code in leagues:
            if not self._load_league_model(league_code):
                continue
            sport_key = LEAGUE_KEY_MAP.get(league_code)
            matches = self.api_client.get_live_odds(sport_key)
            for match in matches:
                match.league = league_code
                self._record_snapshots(match)
                for bet in self._analyze_match(match):
                    tracked = self._track_bet(bet, league_code, active_cache)
                    if tracked:
                        result["bets_tracked"] += 1
                        if tracked["confidence"] in ("high", "medium"):
                            alert_bets.append(bet)
        if send_alerts and self.execution_mode == "live" and alert_bets and self.notifier.is_configured():
            self.notifier.sync_send_alert(alert_bets[:5])
            result["alerts_sent"] = min(5, len(alert_bets))
        self._save_result(result)
        return result

    def _save_result(self, result: Dict):
        path = self.results_dir / "live_results_v3.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Football live runner for the active domestic league scope")
    parser.add_argument("--no-alert", action="store_true")
    parser.add_argument(
        "--leagues",
        nargs="+",
        default=SUPPORTED_LEAGUES,  # Alle Ligen default
        help=f"League codes to check. Supported: {' '.join(SUPPORTED_LEAGUES)}",
    )
    parser.add_argument("--shadow", action="store_true")
    args = parser.parse_args()
    runner = LiveCronRunner(execution_mode="shadow" if args.shadow else os.getenv("EXECUTION_MODE", "live"))
    result = runner.check_live_values(args.leagues, send_alerts=not args.no_alert)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Live runner for Champions League, Europa League and Conference League using cross-league football models."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent / 'src') not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from shared.calibration import MarketCalibration
from shared.closing_line import ClosingLineManager
from shared.feedback_loop import UniversalBetTracker
from shared.model_registry import ModelRegistry
from shared.risk_manager import PortfolioRiskManager
from shared.runtime_utils import canonical_event_key, import_module_from_path, load_env, now_iso
from football.config import UEFA_COMPETITIONS, config
from engine.value_engine import ValueBet, ValueEngine
from model.dixon_coles import DixonColesModel
_odds_module = import_module_from_path('football_theoddsapi', Path(__file__).resolve().parent / 'src' / 'scraper' / 'theoddsapi.py')
TheOddsAPIClient = _odds_module.TheOddsAPIClient
from utils.team_database import ALL_TEAM_MAPPINGS

load_env()

try:
    from notifications.telegram import TelegramNotifier
except Exception:  # pragma: no cover
    TelegramNotifier = None


TEAM_NORMALIZATION = {
    'Manchester City': 'Man City',
    'Manchester United': 'Man United',
    'Tottenham Hotspur': 'Tottenham',
    'Inter Milan': 'Inter',
    'AC Milan': 'Milan',
    'Paris Saint-Germain': 'PSG',
    'Atletico Madrid': 'Atletico Madrid',
    'Sporting Lisbon': 'Sporting CP',
    'Club Brugge KV': 'Club Brugge',
    'Union SG': 'Union Saint-Gilloise',
}


class UEFACompetitionRunner:
    def __init__(self, execution_mode: str = 'live'):
        self.execution_mode = execution_mode
        self.api_client = TheOddsAPIClient()
        self.notifier = TelegramNotifier() if TelegramNotifier else None
        self.tracker = UniversalBetTracker()
        self.calibration = MarketCalibration()
        self.closing = ClosingLineManager()
        self.registry = ModelRegistry()
        self.risk = PortfolioRiskManager(bankroll=float(getattr(config, 'DEFAULT_BANKROLL', 1000.0)))
        self.models_dir = Path('football/models/leagues') if Path('football/models/leagues').exists() else Path('models/leagues')
        self.loaded_models: Dict[str, DixonColesModel] = {}

    def _normalize(self, team: str) -> str:
        return TEAM_NORMALIZATION.get(team, team)

    def _guess_league(self, team: str) -> str:
        team = self._normalize(team)
        if team in ALL_TEAM_MAPPINGS:
            return ALL_TEAM_MAPPINGS[team]
        lower = team.lower()
        for known_team, league in ALL_TEAM_MAPPINGS.items():
            if known_team.lower() in lower or lower in known_team.lower():
                return league
        if any(x in lower for x in ('dortmund', 'leverkusen', 'frankfurt', 'stuttgart', 'bayern')):
            return 'D1'
        if any(x in lower for x in ('liverpool', 'arsenal', 'man ', 'tottenham', 'chelsea', 'villa')):
            return 'E0'
        if any(x in lower for x in ('madrid', 'barcelona', 'sevilla', 'bilbao', 'sociedad', 'betis')):
            return 'SP1'
        if any(x in lower for x in ('inter', 'milan', 'juventus', 'roma', 'atalanta', 'napoli', 'lazio')):
            return 'I1'
        if any(x in lower for x in ('psg', 'lyon', 'marseille', 'lille', 'monaco', 'nice')):
            return 'F1'
        return 'D1'

    def _load_model(self, league_code: str) -> Optional[DixonColesModel]:
        if league_code in self.loaded_models:
            return self.loaded_models[league_code]
        model_path = self.models_dir / f'dixon_coles_{league_code}.pkl'
        if not model_path.exists():
            return None
        model = DixonColesModel.load(model_path)
        self.loaded_models[league_code] = model
        self.registry.ensure_registered_from_file(f'football_{league_code}', model_path)
        return model

    def _predict(self, home_team: str, away_team: str):
        leagues = sorted({self._guess_league(home_team), self._guess_league(away_team)})
        predictions = []
        home_norm = self._normalize(home_team)
        away_norm = self._normalize(away_team)
        for league in leagues:
            model = self._load_model(league)
            if not model:
                continue
            try:
                pred = model.predict(home_norm, away_norm)
            except Exception:
                pred = None
            if pred:
                predictions.append(pred)
        if not predictions:
            return None
        base = predictions[0]
        if len(predictions) == 1:
            pred = base
        else:
            pred = predictions[0]
            pred.prob_home_win = mean([p.prob_home_win for p in predictions])
            pred.prob_draw = mean([p.prob_draw for p in predictions])
            pred.prob_away_win = mean([p.prob_away_win for p in predictions])
            pred.expected_home_goals = mean([getattr(p, 'expected_home_goals', 1.2) for p in predictions])
            pred.expected_away_goals = mean([getattr(p, 'expected_away_goals', 1.1) for p in predictions])
        pred.home_team = home_team
        pred.away_team = away_team
        pred.league = f"UEFA:{'/'.join(leagues)}"
        return pred

    def _market_meta(self, bet: ValueBet) -> Dict:
        line = None
        if str(bet.bet_type).startswith('Over_') or str(bet.bet_type).startswith('Under_'):
            market = 'totals'
            try:
                line = float(str(bet.bet_type).split('_', 1)[1])
            except Exception:
                line = 2.5
        elif bet.bet_type in ('1X', 'X2', '12'):
            market = 'dc'
        else:
            market = '1x2'
        return {'market': market, 'line': line}

    def _record_snapshots(self, competition_code: str, odds_match):
        rows = []
        for bookmaker, odds in odds_match.odds_1.items():
            rows.append({'market': '1x2', 'selection': odds_match.home_team, 'bookmaker': bookmaker, 'odds': odds})
        for bookmaker, odds in odds_match.odds_x.items():
            rows.append({'market': '1x2', 'selection': 'Draw', 'bookmaker': bookmaker, 'odds': odds})
        for bookmaker, odds in odds_match.odds_2.items():
            rows.append({'market': '1x2', 'selection': odds_match.away_team, 'bookmaker': bookmaker, 'odds': odds})
        for bookmaker, odds in odds_match.odds_over.items():
            rows.append({'market': 'totals', 'selection': f'Over {odds_match.ou_line}', 'bookmaker': bookmaker, 'odds': odds, 'line': odds_match.ou_line})
        for bookmaker, odds in odds_match.odds_under.items():
            rows.append({'market': 'totals', 'selection': f'Under {odds_match.ou_line}', 'bookmaker': bookmaker, 'odds': odds, 'line': odds_match.ou_line})
        self.closing.record_candidates('football', odds_match.home_team, odds_match.away_team, odds_match.commence_time.isoformat(), odds_match.event_id, rows)

    def _track_bet(self, bet: ValueBet, competition_code: str, active_cache: List[Dict]) -> Optional[Dict]:
        meta = self._market_meta(bet)
        calibration = self.calibration.adjust_bet('football', meta['market'], bet.kelly_stake, bet.value_percentage, bet.confidence)
        payload = {
            'execution_mode': self.execution_mode,
            'sport': 'football',
            'league': competition_code,
            'match_id': getattr(bet, 'match_id', ''),
            'event_id': canonical_event_key('football', bet.home_team, bet.away_team, bet.match_datetime.isoformat()),
            'home_team': bet.home_team,
            'away_team': bet.away_team,
            'match_date': bet.match_datetime.isoformat(),
            'bet_type': bet.bet_type,
            'market': meta['market'],
            'selection': bet.selection,
            'line': meta['line'],
            'odds': bet.best_odds,
            'opening_odds': bet.best_odds,
            'bookmaker': bet.bookmaker,
            'bookmaker_options': [],
            'model_prob': bet.model_probability,
            'market_prob': bet.market_probability,
            'value_percentage': bet.value_percentage,
            'expected_value': bet.expected_value,
            'raw_kelly_stake': bet.kelly_stake,
            'kelly_stake': calibration['adjusted_stake'],
            'confidence': calibration['adjusted_confidence'],
            'stake_multiplier': calibration['stake_multiplier'],
            'calibration_version': self.calibration.profile.get('version', 'v3'),
            'model_version': f'uefa-hybrid-v6-{competition_code.lower()}',
            'feature_set_version': 'v6.uefa-pipeline',
            'data_version': 'v6.uefa-pipeline',
            'thresholds_version': 'v6.uefa-pipeline',
            'odds_timestamp': bet.odds_timestamp or now_iso(),
        }
        dedupe_key = (payload['event_id'], payload['market'], payload['selection'])
        if dedupe_key in {(b.get('event_id'), b.get('market'), b.get('selection')) for b in active_cache}:
            return None
        risk = self.risk.evaluate_bet(payload, active_cache)
        if not risk.approved:
            return None
        payload['risk_status'] = risk.status
        payload['risk_reasons'] = risk.reasons
        payload['kelly_stake'] = risk.approved_stake
        payload['stake_multiplier'] = round(payload['stake_multiplier'] * risk.stake_multiplier, 3)
        self.tracker.place_bet(payload, sport='football')
        active_cache.append(payload)
        return payload

    def run(self, competitions: List[str], send_alerts: bool = True) -> Dict:
        result = {'timestamp': now_iso(), 'execution_mode': self.execution_mode, 'competitions': competitions, 'bets_tracked': 0, 'alerts_sent': 0}
        active_cache = self.tracker.get_active_bets(sport='football')
        alerts: List[ValueBet] = []
        for code in competitions:
            info = UEFA_COMPETITIONS.get(code)
            if not info:
                continue
            matches = self.api_client.get_live_odds(info['sport_key'])
            engine = ValueEngine(historical_performance=self.tracker.calculate_performance(days=90, sport='football', execution_mode=self.execution_mode))
            for match in matches:
                match.league = info['name']
                self._record_snapshots(code, match)
                pred = self._predict(match.home_team, match.away_team)
                if not pred:
                    continue
                for bet in engine.analyze_match(pred, match):
                    tracked = self._track_bet(bet, code, active_cache)
                    if tracked:
                        result['bets_tracked'] += 1
                        if tracked['confidence'] in ('high', 'medium'):
                            alerts.append(bet)
        if send_alerts and self.execution_mode == 'live' and alerts and self.notifier and self.notifier.is_configured():
            self.notifier.sync_send_alert(alerts[:5])
            result['alerts_sent'] = min(5, len(alerts))
        return result


def main():
    parser = argparse.ArgumentParser(description='UEFA live runner for Champions League, Europa League and Conference League')
    parser.add_argument('--execution-mode', choices=['live', 'shadow'], default='live')
    parser.add_argument('--competitions', nargs='+', default=['UCL', 'UEL', 'UECL'])
    parser.add_argument('--no-alerts', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    runner = UEFACompetitionRunner(execution_mode=args.execution_mode)
    result = runner.run(args.competitions, send_alerts=not args.no_alerts)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"UEFA checked: {', '.join(result['competitions'])} | bets={result['bets_tracked']} | alerts={result['alerts_sent']}")


if __name__ == '__main__':
    main()

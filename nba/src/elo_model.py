"""
NBA ELO Rating Model v2
- Fixed training window (150 games, not 30)
- Proper season regression between seasons
- Spread cover probability estimation
- Totals (pace-adjusted) probability estimation
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from scipy.stats import norm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NBAEloModel:
    """
    ELO-based NBA prediction model with:
    - Margin-of-victory adjustment
    - Home court advantage
    - Season-to-season regression
    - Spread & Totals probability estimation (NEW)
    """

    def __init__(self,
                 initial_elo: float = 1500,
                 k_factor: float = 20,
                 home_advantage: float = 100,
                 margin_mult: float = 1.0,
                 season_regression: float = 0.25):
        self.initial_elo = initial_elo
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.margin_mult = margin_mult
        self.season_regression = season_regression
        self.elos = {}
        self.history = []

        # Pace & scoring data for totals (NEW)
        self.team_pace = {}       # {team: possessions_per_game}
        self.team_ortg = {}       # {team: offensive_rating}
        self.team_drtg = {}       # {team: defensive_rating}
        self.league_avg_pace = 100.0
        self.league_avg_ortg = 112.0

    def get_elo(self, team: str) -> float:
        if team not in self.elos:
            self.elos[team] = {"elo": self.initial_elo, "games": 0}
        return self.elos[team]["elo"]

    def expected_score(self, elo_diff: float) -> float:
        return 1 / (1 + 10 ** (-elo_diff / 400))

    def margin_factor(self, margin: int) -> float:
        """Log-based margin factor: larger victories count more."""
        return np.log(1 + abs(margin)) * self.margin_mult

    def apply_season_regression(self):
        """
        Regress all Elo ratings toward the mean between seasons.
        Should be called once at season boundary.
        """
        if not self.elos:
            return

        mean_elo = np.mean([d["elo"] for d in self.elos.values()])
        logger.info(f"Season regression: mean={mean_elo:.0f}, factor={self.season_regression}")

        for team in self.elos:
            old = self.elos[team]["elo"]
            self.elos[team]["elo"] = old * (1 - self.season_regression) + mean_elo * self.season_regression
            logger.debug(f"  {team}: {old:.0f} -> {self.elos[team]['elo']:.0f}")

    def update_game(self, home_team: str, away_team: str,
                    home_score: int, away_score: int,
                    date: str = None) -> Dict:
        home_elo = self.get_elo(home_team)
        away_elo = self.get_elo(away_team)

        elo_diff_home = home_elo - away_elo + self.home_advantage
        home_expected = self.expected_score(elo_diff_home)
        away_expected = 1 - home_expected

        home_won = home_score > away_score
        home_actual = 1.0 if home_won else 0.0

        margin = abs(home_score - away_score)
        mov_factor = self.margin_factor(margin)
        k = self.k_factor * mov_factor

        home_change = k * (home_actual - home_expected)
        away_change = k * ((1 - home_actual) - away_expected)

        new_home = home_elo + home_change
        new_away = away_elo + away_change

        self.elos[home_team] = {"elo": new_home, "games": self.elos[home_team].get("games", 0) + 1}
        self.elos[away_team] = {"elo": new_away, "games": self.elos[away_team].get("games", 0) + 1}

        # Update pace/rating stats (NEW)
        self._update_scoring_stats(home_team, away_team, home_score, away_score)

        result = {
            "date": date, "home_team": home_team, "away_team": away_team,
            "home_score": home_score, "away_score": away_score,
            "home_elo_pre": home_elo, "away_elo_pre": away_elo,
            "home_elo_post": new_home, "away_elo_post": new_away,
            "home_elo_change": home_change, "away_elo_change": away_change,
            "home_expected": home_expected, "margin": home_score - away_score,
        }
        self.history.append(result)
        return result

    def _update_scoring_stats(self, home: str, away: str, hs: int, as_: int):
        """Track pace and efficiency for totals model."""
        # Simplified: use scoring as proxy for pace
        total = hs + as_
        est_pace = total / 2.0  # rough possessions estimate

        for team, scored, allowed in [(home, hs, as_), (away, as_, hs)]:
            alpha = 0.15  # exponential smoothing
            old_pace = self.team_pace.get(team, self.league_avg_pace)
            old_ortg = self.team_ortg.get(team, self.league_avg_ortg)
            old_drtg = self.team_drtg.get(team, self.league_avg_ortg)

            self.team_pace[team] = (1 - alpha) * old_pace + alpha * est_pace
            self.team_ortg[team] = (1 - alpha) * old_ortg + alpha * (scored / est_pace * 100 if est_pace > 0 else old_ortg)
            self.team_drtg[team] = (1 - alpha) * old_drtg + alpha * (allowed / est_pace * 100 if est_pace > 0 else old_drtg)

    def train(self, games: pd.DataFrame, max_games: int = 150) -> "NBAEloModel":
        """
        Train on historical games.
        FIXED: Default 150 games (roughly a full season), was 30.
        Set max_games=0 for all games.
        """
        games = games.sort_values("date", ascending=False).reset_index(drop=True)

        if max_games > 0 and len(games) > max_games:
            games = games.head(max_games)
            logger.info(f"Training window: {max_games} most recent games")

        games = games.sort_values("date").reset_index(drop=True)
        logger.info(f"Training ELO on {len(games)} games...")

        # Detect season boundaries for regression
        prev_season = None
        for idx, game in games.iterrows():
            current_season = self._extract_season(game.get("date"))
            if prev_season and current_season != prev_season:
                logger.info(f"Season boundary: {prev_season} -> {current_season}")
                self.apply_season_regression()
            prev_season = current_season

            self.update_game(
                home_team=game["home_team"], away_team=game["away_team"],
                home_score=int(game["home_score"]), away_score=int(game["away_score"]),
                date=game.get("date"))

        logger.info(f"Training complete. {len(self.elos)} teams tracked.")
        return self

    def _extract_season(self, date_val) -> Optional[str]:
        """Extract season string from date (e.g. '2025-26')."""
        try:
            if isinstance(date_val, str):
                dt = datetime.fromisoformat(date_val[:10])
            elif hasattr(date_val, 'year'):
                dt = date_val
            else:
                return None
            year = dt.year
            month = dt.month
            # NBA season: Oct-Jun. If Oct+, season starts this year
            if month >= 10:
                return f"{year}-{year+1}"
            else:
                return f"{year-1}-{year}"
        except Exception:
            return None

    def predict(self, home_team: str, away_team: str) -> Dict:
        home_elo = self.get_elo(home_team)
        away_elo = self.get_elo(away_team)
        elo_diff = home_elo - away_elo + self.home_advantage

        home_win_prob = self.expected_score(elo_diff)
        return {
            "home_team": home_team, "away_team": away_team,
            "home_elo": home_elo, "away_elo": away_elo,
            "elo_diff": elo_diff,
            "home_win_prob": home_win_prob,
            "away_win_prob": 1 - home_win_prob,
            "home_advantage": self.home_advantage,
        }

    def predict_with_injuries(self, home_team: str, away_team: str,
                              home_impact: Dict, away_impact: Dict) -> Dict:
        base = self.predict(home_team, away_team)
        h_adj = home_impact.get('impact_score', 0) * 0.8
        a_adj = away_impact.get('impact_score', 0) * 0.8
        elo_diff = (base['home_elo'] - h_adj) - (base['away_elo'] - a_adj) + self.home_advantage
        return {
            **base,
            "home_elo_adj": base['home_elo'] - h_adj,
            "away_elo_adj": base['away_elo'] - a_adj,
            "elo_diff": elo_diff,
            "home_win_prob": self.expected_score(elo_diff),
            "away_win_prob": 1 - self.expected_score(elo_diff),
            "injury_adjusted": True,
        }

    # ── SPREAD PROBABILITY (NEW) ────────────────

    def predict_spread_cover(self, home_team: str, away_team: str,
                             spread: float) -> float:
        """
        Probability that home team covers the spread.
        Uses Elo-derived expected margin + normal distribution.

        Args:
            spread: e.g. -5.5 means home favored by 5.5
        Returns:
            P(home covers)
        """
        pred = self.predict(home_team, away_team)
        # Convert win probability to expected margin
        # Empirical: ~0.03 win prob ≈ 1 point margin in NBA
        expected_margin = (pred['home_win_prob'] - 0.5) / 0.03

        # NBA game-to-game standard deviation ~ 12 points
        std_dev = 12.0
        # P(actual_margin > -spread) = P(actual_margin + spread > 0)
        z = (expected_margin + spread) / std_dev
        return float(norm.cdf(z))

    # ── TOTALS PROBABILITY (NEW) ────────────────

    def predict_total(self, home_team: str, away_team: str,
                      line: float = 220.0) -> Dict:
        """
        Pace-adjusted total points prediction.

        Returns:
            {'expected_total': float, 'over_prob': float, 'under_prob': float}
        """
        h_pace = self.team_pace.get(home_team, self.league_avg_pace)
        a_pace = self.team_pace.get(away_team, self.league_avg_pace)
        h_ortg = self.team_ortg.get(home_team, self.league_avg_ortg)
        a_ortg = self.team_ortg.get(away_team, self.league_avg_ortg)
        h_drtg = self.team_drtg.get(home_team, self.league_avg_ortg)
        a_drtg = self.team_drtg.get(away_team, self.league_avg_ortg)

        # Expected pace for the matchup
        game_pace = (h_pace + a_pace) / 2.0

        # Expected points: (ORtg_team * DRtg_opp / league_avg) * pace / 100
        if self.league_avg_ortg > 0:
            home_pts = (h_ortg * a_drtg / self.league_avg_ortg) * game_pace / 100
            away_pts = (a_ortg * h_drtg / self.league_avg_ortg) * game_pace / 100
        else:
            home_pts = away_pts = 110.0

        expected_total = home_pts + away_pts

        # P(Over): Normal distribution, std_dev ~ 12 for NBA totals
        std_dev = 12.0
        z = (line - expected_total) / std_dev
        over_prob = float(1 - norm.cdf(z))
        under_prob = float(norm.cdf(z))

        return {
            'expected_total': round(expected_total, 1),
            'home_pts': round(home_pts, 1),
            'away_pts': round(away_pts, 1),
            'game_pace': round(game_pace, 1),
            'over_prob': over_prob,
            'under_prob': under_prob,
            'line': line,
        }

    # ── RANKINGS ─────────────────────────────────

    def get_rankings(self) -> pd.DataFrame:
        rankings = []
        for team, data in self.elos.items():
            rankings.append({
                "team": team, "elo": data["elo"], "games": data.get("games", 0),
                "pace": self.team_pace.get(team, 0),
                "ortg": round(self.team_ortg.get(team, 0), 1),
                "drtg": round(self.team_drtg.get(team, 0), 1),
            })
        df = pd.DataFrame(rankings)
        df = df.sort_values("elo", ascending=False).reset_index(drop=True)
        df["rank"] = df.index + 1
        return df

    # ── PERSISTENCE ──────────────────────────────

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({
                "elos": self.elos, "history": self.history,
                "team_pace": self.team_pace,
                "team_ortg": self.team_ortg,
                "team_drtg": self.team_drtg,
                "config": {
                    "initial_elo": self.initial_elo, "k_factor": self.k_factor,
                    "home_advantage": self.home_advantage,
                    "margin_mult": self.margin_mult,
                    "season_regression": self.season_regression,
                }
            }, f)
        logger.info(f"Model saved: {path}")

    @classmethod
    def load(cls, path: str) -> "NBAEloModel":
        with open(path, "rb") as f:
            data = pickle.load(f)
        c = data.get("config", {})
        model = cls(
            initial_elo=c.get("initial_elo", 1500),
            k_factor=c.get("k_factor", 20),
            home_advantage=c.get("home_advantage", 100),
            margin_mult=c.get("margin_mult", 1.0),
            season_regression=c.get("season_regression", 0.25),
        )
        model.elos = data["elos"]
        model.history = data.get("history", [])
        model.team_pace = data.get("team_pace", {})
        model.team_ortg = data.get("team_ortg", {})
        model.team_drtg = data.get("team_drtg", {})
        logger.info(f"Model loaded: {path} ({len(model.elos)} teams)")
        return model

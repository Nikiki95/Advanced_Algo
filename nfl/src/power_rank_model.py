"""
NFL Power Ranking Model v2
- Regression only between seasons (not every game update)
- Full season training window (17 games)
- Totals prediction via scoring model
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from typing import Dict, Optional
from scipy.stats import norm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NFLPowerModel:
    """
    NFL model based on Power Rankings + EPA + Home Field Advantage.
    FIXED: Regression only applied between seasons.
    """

    def __init__(self,
                 home_advantage: float = 2.5,
                 inter_season_regression: float = 0.30,
                 learning_rate: float = 0.30,
                 spread_std_dev: float = 12.0):
        self.home_advantage = home_advantage
        self.inter_season_regression = inter_season_regression
        self.learning_rate = learning_rate
        self.spread_std_dev = spread_std_dev
        self.ratings = {}
        self.power_scores = {}
        self.scoring_stats = {}  # NEW: for totals
        self.history = []

    def get_rating(self, team: str) -> Dict:
        if team not in self.ratings:
            self.ratings[team] = {"offense": 0, "defense": 0}
        return self.ratings[team]

    def get_power_score(self, team: str) -> float:
        if team not in self.power_scores:
            self.power_scores[team] = 0.0
        return self.power_scores[team]

    def apply_season_regression(self):
        """
        Regress all power scores toward 0 between seasons.
        Called ONCE at season boundary, NOT every game.
        """
        logger.info(f"Applying inter-season regression ({self.inter_season_regression})")
        for team in self.power_scores:
            old = self.power_scores[team]
            self.power_scores[team] = old * (1 - self.inter_season_regression)
            logger.debug(f"  {team}: {old:.2f} -> {self.power_scores[team]:.2f}")

    def predict_spread(self, home_team: str, away_team: str) -> Dict:
        home_power = self.get_power_score(home_team)
        away_power = self.get_power_score(away_team)
        expected_spread = self.home_advantage + (home_power - away_power)
        home_cover_prob = self._spread_probability(expected_spread)
        home_win_prob = home_cover_prob * 0.95 + 0.025

        return {
            "home_team": home_team, "away_team": away_team,
            "home_power": home_power, "away_power": away_power,
            "expected_spread": expected_spread,
            "home_cover_prob": home_cover_prob,
            "away_cover_prob": 1 - home_cover_prob,
            "home_win_prob": home_win_prob,
            "away_win_prob": 1 - home_win_prob,
        }

    def predict_total(self, home_team: str, away_team: str,
                      line: float = 45.0) -> Dict:
        """
        NEW: Total points prediction based on team scoring stats.
        """
        h_stats = self.scoring_stats.get(home_team, {'ppg': 22.0, 'papg': 21.0})
        a_stats = self.scoring_stats.get(away_team, {'ppg': 22.0, 'papg': 21.0})

        # Expected points: avg of team's offense and opponent's defense allowed
        home_pts = (h_stats['ppg'] + a_stats['papg']) / 2 + self.home_advantage / 2
        away_pts = (a_stats['ppg'] + h_stats['papg']) / 2 - self.home_advantage / 2

        expected_total = home_pts + away_pts

        # P(Over): Normal approximation, std_dev ~ 10 for NFL
        std_dev = 10.0
        z = (line - expected_total) / std_dev
        over_prob = float(1 - norm.cdf(z))

        return {
            'expected_total': round(expected_total, 1),
            'home_pts': round(home_pts, 1),
            'away_pts': round(away_pts, 1),
            'over_prob': over_prob,
            'under_prob': 1 - over_prob,
            'line': line,
        }

    def _spread_probability(self, spread: float) -> float:
        z = -spread / self.spread_std_dev
        return float(1 - norm.cdf(z))

    def update_ratings(self, home_team: str, away_team: str,
                       home_score: int, away_score: int,
                       week: int = None) -> Dict:
        home_power = self.get_power_score(home_team)
        away_power = self.get_power_score(away_team)
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        expected_spread = self.home_advantage + (home_power - away_power)
        actual_spread = home_score - away_score
        error = actual_spread - expected_spread

        # Update power scores — NO regression here (FIXED)
        home_power_new = home_power + self.learning_rate * error * 0.5
        away_power_new = away_power - self.learning_rate * error * 0.5

        self.power_scores[home_team] = home_power_new
        self.power_scores[away_team] = away_power_new

        # Offense/Defense ratings
        alpha = 0.3
        home_rating["offense"] = (1 - alpha) * home_rating["offense"] + alpha * (home_score - self.home_advantage)
        home_rating["defense"] = (1 - alpha) * home_rating["defense"] + alpha * (away_score - self.home_advantage)
        away_rating["offense"] = (1 - alpha) * away_rating["offense"] + alpha * away_score
        away_rating["defense"] = (1 - alpha) * away_rating["defense"] + alpha * home_score

        # Scoring stats for totals (NEW)
        for team, scored, allowed in [(home_team, home_score, away_score), (away_team, away_score, home_score)]:
            if team not in self.scoring_stats:
                self.scoring_stats[team] = {'ppg': 22.0, 'papg': 21.0, 'games': 0}
            s = self.scoring_stats[team]
            n = s['games'] + 1
            s['ppg'] = ((s['ppg'] * s['games']) + scored) / n
            s['papg'] = ((s['papg'] * s['games']) + allowed) / n
            s['games'] = n

        result = {
            "week": week, "home_team": home_team, "away_team": away_team,
            "home_score": home_score, "away_score": away_score,
            "home_power_pre": home_power, "away_power_pre": away_power,
            "home_power_post": home_power_new, "away_power_post": away_power_new,
            "expected_spread": expected_spread, "actual_spread": actual_spread,
            "error": error,
        }
        self.history.append(result)
        return result

    def train(self, games: pd.DataFrame, max_weeks: int = 17) -> "NFLPowerModel":
        """
        Train on historical games.
        FIXED: Default 17 weeks (full regular season), was 8.
        """
        if 'week' in games.columns:
            games = games.sort_values("week", ascending=False).reset_index(drop=True)
        if max_weeks > 0 and 'week' in games.columns:
            max_week = games['week'].max()
            cutoff = max(1, max_week - max_weeks + 1)
            games = games[games['week'] >= cutoff]

        if 'week' in games.columns:
            games = games.sort_values("week").reset_index(drop=True)

        logger.info(f"Training NFL Power Model on {len(games)} games...")

        # Season boundary detection
        prev_season = None
        for idx, game in games.iterrows():
            curr = game.get("season")
            if prev_season and curr and curr != prev_season:
                self.apply_season_regression()
            prev_season = curr

            self.update_ratings(
                home_team=game["home_team"], away_team=game["away_team"],
                home_score=int(game["home_score"]), away_score=int(game["away_score"]),
                week=game.get("week"))

        logger.info(f"Training complete. {len(self.power_scores)} teams.")
        return self

    def get_rankings(self) -> pd.DataFrame:
        rankings = []
        for team, score in self.power_scores.items():
            r = self.get_rating(team)
            s = self.scoring_stats.get(team, {})
            rankings.append({
                "team": team, "power": score,
                "offense": r["offense"], "defense": r["defense"],
                "net_rating": r["offense"] - r["defense"],
                "ppg": round(s.get('ppg', 0), 1),
                "papg": round(s.get('papg', 0), 1),
            })
        df = pd.DataFrame(rankings)
        df = df.sort_values("power", ascending=False).reset_index(drop=True)
        df["rank"] = df.index + 1
        return df

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({
                "power_scores": self.power_scores, "ratings": self.ratings,
                "scoring_stats": self.scoring_stats, "history": self.history,
                "config": {
                    "home_advantage": self.home_advantage,
                    "inter_season_regression": self.inter_season_regression,
                    "learning_rate": self.learning_rate,
                    "spread_std_dev": self.spread_std_dev,
                }
            }, f)

    @classmethod
    def load(cls, path: str) -> "NFLPowerModel":
        with open(path, "rb") as f:
            data = pickle.load(f)
        c = data.get("config", {})
        model = cls(
            home_advantage=c.get("home_advantage", 2.5),
            inter_season_regression=c.get("inter_season_regression", 0.30),
            learning_rate=c.get("learning_rate", 0.30),
            spread_std_dev=c.get("spread_std_dev", 12.0),
        )
        model.power_scores = data["power_scores"]
        model.ratings = data.get("ratings", {})
        model.scoring_stats = data.get("scoring_stats", {})
        model.history = data.get("history", [])
        return model

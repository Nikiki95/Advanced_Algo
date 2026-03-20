"""
Dixon-Coles Model v2

Changes from v1:
- xG-based training mode (uses expected goals instead of actual goals)
- Adaptive time-decay per league
- Promoted team handling (inherit ratings from lower division)
- Both penaltyblog and fallback implementations support xG
"""
import pickle
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy.stats import poisson

try:
    import penaltyblog as pb
    PENALTYBLOG_AVAILABLE = True
except ImportError:
    PENALTYBLOG_AVAILABLE = False
    print("[WARN] penaltyblog not installed — using fallback Poisson")


@dataclass
class TeamStrength:
    team: str
    attack: float
    defense: float
    home_advantage: float


@dataclass
class MatchPrediction:
    home_team: str
    away_team: str
    league: str
    match_date: datetime
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    expected_home_goals: float
    expected_away_goals: float
    score_matrix: Optional[np.ndarray] = None

    @property
    def outcome_probs(self) -> Dict[str, float]:
        return {'1': self.prob_home_win, 'X': self.prob_draw, '2': self.prob_away_win}


class DixonColesModel:
    """
    Dixon-Coles with xG support.

    Training modes:
    - goals: Traditional (FTHG/FTAG) — default, works with penaltyblog
    - xg: Expected goals (xHG/xAG) — more stable ratings, uses Poisson fallback

    Predictions always use the Poisson score-matrix approach.
    """

    # Adaptive decay presets per league type
    DECAY_PRESETS = {
        'high_turnover': 0.005,   # Bundesliga, Ligue 1 (lots of player movement)
        'stable': 0.003,          # Premier League, La Liga (more stable squads)
        'default': 0.0035,        # Everything else
        'lower_division': 0.006,  # 2. Bundesliga and comparable leagues (more variance)
    }

    LEAGUE_DECAY_MAP = {
        'D1': 'high_turnover', 'D2': 'lower_division',
        'E0': 'stable',
        'SP1': 'stable', 'I1': 'stable',
        'F1': 'high_turnover', 'P1': 'default',
        'N1': 'default',
    }

    # Typical rating adjustment for newly promoted teams
    PROMOTION_DISCOUNT = 0.85  # 15% weaker than league average

    def __init__(self, rho: float = -0.13, decay: float = None,
                 league_code: str = None, training_mode: str = 'xg'):
        """
        Args:
            rho: Dixon-Coles low-score correlation parameter
            decay: Time-decay (None = auto from league)
            league_code: For adaptive decay selection
            training_mode: 'xg' or 'goals'
        """
        self.rho = rho
        self.league_code = league_code
        self.training_mode = training_mode

        # Auto-select decay
        if decay is not None:
            self.decay = decay
        elif league_code:
            preset = self.LEAGUE_DECAY_MAP.get(league_code, 'default')
            self.decay = self.DECAY_PRESETS[preset]
        else:
            self.decay = self.DECAY_PRESETS['default']

        self.fitted_model = None
        self.team_ratings: Dict[str, TeamStrength] = {}
        self.training_date: Optional[datetime] = None

        # xG training state
        self.avg_home = 1.5
        self.avg_away = 1.2
        self.home_advantage = 0.55

    def _calculate_time_weights(self, df: pd.DataFrame) -> np.ndarray:
        if 'Date' not in df.columns:
            return np.ones(len(df))
        dates = pd.to_datetime(df['Date'])
        most_recent = dates.max()
        days_ago = (most_recent - dates).dt.days
        return np.exp(-self.decay * days_ago)

    # ────────────────────────────────────────────
    # TRAINING
    # ────────────────────────────────────────────

    def fit(self, df: pd.DataFrame, promoted_teams: List[str] = None) -> 'DixonColesModel':
        """
        Train the model.

        Args:
            df: DataFrame with Date, HomeTeam, AwayTeam, FTHG, FTAG,
                and optionally xHG, xAG for xG mode
            promoted_teams: Teams newly promoted (get discounted ratings)
        """
        mode = self.training_mode

        # Determine which columns to use
        if mode == 'xg' and 'xHG' in df.columns:
            home_col, away_col = 'xHG', 'xAG'
            print(f"[Model] Training on xG data ({len(df)} matches, decay={self.decay})")
        else:
            home_col, away_col = 'FTHG', 'FTAG'
            if mode == 'xg':
                print(f"[Model] xG columns not found, falling back to actual goals")
            print(f"[Model] Training on actual goals ({len(df)} matches, decay={self.decay})")

        # For xG (float values), always use the Poisson fallback
        # penaltyblog expects integer goals
        if mode == 'xg' and 'xHG' in df.columns:
            return self._fit_xg(df, home_col, away_col, promoted_teams)

        # For integer goals, try penaltyblog first
        if PENALTYBLOG_AVAILABLE and mode != 'xg':
            return self._fit_penaltyblog(df, promoted_teams)

        return self._fit_poisson(df, home_col, away_col, promoted_teams)

    def _fit_xg(self, df: pd.DataFrame, home_col: str, away_col: str,
                promoted_teams: List[str] = None) -> 'DixonColesModel':
        """
        Train on xG values using weighted Poisson approach.
        xG values are floats, so we use regression-style fitting.
        """
        weights = self._calculate_time_weights(df)

        # Weighted averages
        total_w = weights.sum()
        self.avg_home = float((df[home_col].values * weights).sum() / total_w)
        self.avg_away = float((df[away_col].values * weights).sum() / total_w)
        self.home_advantage = self.avg_home / (self.avg_home + self.avg_away)

        teams = set(df['HomeTeam']).union(set(df['AwayTeam']))

        for team in teams:
            home_mask = df['HomeTeam'] == team
            away_mask = df['AwayTeam'] == team

            home_games = df[home_mask]
            away_games = df[away_mask]
            hw = weights[home_mask.values]
            aw = weights[away_mask.values]

            if len(home_games) > 0 and len(away_games) > 0:
                # Weighted attack strength (xG scored)
                home_scored = (home_games[home_col].values * hw).sum() / hw.sum()
                away_scored = (away_games[away_col].values * aw).sum() / aw.sum()

                # Weighted defense strength (xG conceded)
                home_conceded = (home_games[away_col].values * hw).sum() / hw.sum()
                away_conceded = (away_games[home_col].values * aw).sum() / aw.sum()

                attack = ((home_scored / self.avg_home) + (away_scored / self.avg_away)) / 2
                defense = ((home_conceded / self.avg_away) + (away_conceded / self.avg_home)) / 2
            else:
                attack = 1.0
                defense = 1.0

            self.team_ratings[team] = TeamStrength(
                team=team, attack=attack,
                defense=defense, home_advantage=self.home_advantage)

        # Handle promoted teams
        if promoted_teams:
            self._apply_promotion_discount(promoted_teams)

        self.training_date = datetime.now()
        print(f"[Model] xG training complete. {len(self.team_ratings)} teams. "
              f"Avg xG: {self.avg_home:.2f} / {self.avg_away:.2f}")
        return self

    def _fit_penaltyblog(self, df: pd.DataFrame,
                         promoted_teams: List[str] = None) -> 'DixonColesModel':
        """Train using penaltyblog (integer goals only)."""
        print(f"[Model] Training Dixon-Coles via penaltyblog on {len(df)} matches...")
        weights = self._calculate_time_weights(df)

        self.fitted_model = pb.models.DixonColesGoalModel(
            goals_home=df['FTHG'].astype(int).values,
            goals_away=df['FTAG'].astype(int).values,
            teams_home=df['HomeTeam'].values,
            teams_away=df['AwayTeam'].values,
            weights=weights)
        self.fitted_model.fit()

        self._extract_penaltyblog_ratings()
        if promoted_teams:
            self._apply_promotion_discount(promoted_teams)

        self.training_date = datetime.now()
        print(f"[Model] penaltyblog training complete. {len(self.team_ratings)} teams.")
        return self

    def _fit_poisson(self, df: pd.DataFrame, home_col: str, away_col: str,
                     promoted_teams: List[str] = None) -> 'DixonColesModel':
        """Poisson fallback for integer goals."""
        print(f"[Model] Fallback Poisson on {len(df)} matches...")
        weights = self._calculate_time_weights(df)
        total_w = weights.sum()

        self.avg_home = float((df[home_col].astype(float).values * weights).sum() / total_w)
        self.avg_away = float((df[away_col].astype(float).values * weights).sum() / total_w)
        self.home_advantage = self.avg_home / (self.avg_home + self.avg_away)

        teams = set(df['HomeTeam']).union(set(df['AwayTeam']))
        for team in teams:
            home_mask = df['HomeTeam'] == team
            away_mask = df['AwayTeam'] == team
            hg = df[home_mask]
            ag = df[away_mask]
            hw = weights[home_mask.values]
            aw = weights[away_mask.values]

            if len(hg) > 0 and len(ag) > 0:
                hs = (hg[home_col].astype(float).values * hw).sum() / hw.sum()
                as_ = (ag[away_col].astype(float).values * aw).sum() / aw.sum()
                hc = (hg[away_col].astype(float).values * hw).sum() / hw.sum()
                ac = (ag[home_col].astype(float).values * aw).sum() / aw.sum()

                attack = ((hs / self.avg_home) + (as_ / self.avg_away)) / 2
                defense = ((hc / self.avg_away) + (ac / self.avg_home)) / 2
            else:
                attack = defense = 1.0

            self.team_ratings[team] = TeamStrength(
                team=team, attack=attack, defense=defense,
                home_advantage=self.home_advantage)

        if promoted_teams:
            self._apply_promotion_discount(promoted_teams)

        self.training_date = datetime.now()
        print(f"[Model] Poisson training complete. {len(self.team_ratings)} teams.")
        return self

    def _extract_penaltyblog_ratings(self):
        """Extract ratings from penaltyblog fitted model."""
        if self.fitted_model is None:
            return
        try:
            params = self.fitted_model.get_params()
            home_adv = params.get('home_advantage', 0.0)
            teams = set()
            for key in params.keys():
                if key.startswith('attack_'):
                    teams.add(key[7:])
            for team in teams:
                self.team_ratings[team] = TeamStrength(
                    team=team,
                    attack=params.get(f'attack_{team}', 1.0),
                    defense=params.get(f'defence_{team}', 1.0),
                    home_advantage=home_adv)
        except Exception as e:
            print(f"[Warn] Could not extract ratings: {e}")

    def _apply_promotion_discount(self, promoted_teams: List[str]):
        """
        Newly promoted teams get discounted ratings.
        If they're not yet in the model, create average ratings with discount.
        """
        if not self.team_ratings:
            return

        avg_attack = np.mean([r.attack for r in self.team_ratings.values()])
        avg_defense = np.mean([r.defense for r in self.team_ratings.values()])

        for team in promoted_teams:
            if team in self.team_ratings:
                # Already known: apply discount
                r = self.team_ratings[team]
                r.attack *= self.PROMOTION_DISCOUNT
                r.defense /= self.PROMOTION_DISCOUNT  # Worse defense
            else:
                # New team: create discounted average
                self.team_ratings[team] = TeamStrength(
                    team=team,
                    attack=avg_attack * self.PROMOTION_DISCOUNT,
                    defense=avg_defense / self.PROMOTION_DISCOUNT,
                    home_advantage=self.home_advantage)
            print(f"[Model] Promotion discount applied to {team}")

    # ────────────────────────────────────────────
    # PREDICTION
    # ────────────────────────────────────────────

    def predict(self, home_team: str, away_team: str,
                match_date: Optional[datetime] = None) -> Optional[MatchPrediction]:
        """Predict match outcome."""
        # Try penaltyblog first
        if self.fitted_model is not None:
            return self._predict_penaltyblog(home_team, away_team, match_date)

        # Poisson fallback
        return self._predict_poisson(home_team, away_team, match_date)

    def _predict_penaltyblog(self, home: str, away: str,
                              match_date: Optional[datetime]) -> Optional[MatchPrediction]:
        if home not in self.team_ratings or away not in self.team_ratings:
            return self._predict_poisson(home, away, match_date)

        try:
            grid = self.fitted_model.predict(home, away)
            prob_home = float(grid.home_win)
            prob_draw = float(grid.draw)
            prob_away = float(grid.away_win)

            try:
                hd = grid.home_goal_distribution
                ad = grid.away_goal_distribution
                xg_h = sum(i * p for i, p in enumerate(hd))
                xg_a = sum(i * p for i, p in enumerate(ad))
            except Exception:
                xg_h = xg_a = 1.5

            return MatchPrediction(
                home_team=home, away_team=away, league="",
                match_date=match_date or datetime.now(),
                prob_home_win=prob_home, prob_draw=prob_draw,
                prob_away_win=prob_away,
                expected_home_goals=xg_h, expected_away_goals=xg_a)
        except Exception:
            return self._predict_poisson(home, away, match_date)

    def _predict_poisson(self, home: str, away: str,
                          match_date: Optional[datetime] = None) -> Optional[MatchPrediction]:
        """Poisson prediction using team ratings."""
        if home not in self.team_ratings or away not in self.team_ratings:
            return None

        hr = self.team_ratings[home]
        ar = self.team_ratings[away]

        lambda_h = max(0.1, self.avg_home * hr.attack * ar.defense)
        lambda_a = max(0.1, self.avg_away * ar.attack * hr.defense * (1 - self.home_advantage))

        max_g = 7
        score_matrix = np.zeros((max_g + 1, max_g + 1))
        for i in range(max_g + 1):
            for j in range(max_g + 1):
                p = poisson.pmf(i, lambda_h) * poisson.pmf(j, lambda_a)
                # Dixon-Coles correction for low scores
                if i == 0 and j == 0:
                    p *= 1 - lambda_h * lambda_a * self.rho
                elif i == 0 and j == 1:
                    p *= 1 + lambda_h * self.rho
                elif i == 1 and j == 0:
                    p *= 1 + lambda_a * self.rho
                elif i == 1 and j == 1:
                    p *= 1 - self.rho
                score_matrix[i, j] = max(0, p)

        # Normalize
        total = score_matrix.sum()
        if total > 0:
            score_matrix /= total

        prob_home = float(np.sum(np.tril(score_matrix, -1)))
        prob_draw = float(np.sum(np.diag(score_matrix)))
        prob_away = float(np.sum(np.triu(score_matrix, 1)))

        # Re-normalize probabilities
        s = prob_home + prob_draw + prob_away
        if s > 0:
            prob_home /= s
            prob_draw /= s
            prob_away /= s

        return MatchPrediction(
            home_team=home, away_team=away, league="",
            match_date=match_date or datetime.now(),
            prob_home_win=prob_home, prob_draw=prob_draw,
            prob_away_win=prob_away,
            expected_home_goals=float(lambda_h),
            expected_away_goals=float(lambda_a),
            score_matrix=score_matrix)

    def predict_matches(self, fixtures_df: pd.DataFrame) -> List[MatchPrediction]:
        predictions = []
        for _, row in fixtures_df.iterrows():
            pred = self.predict(
                home_team=row['HomeTeam'], away_team=row['AwayTeam'],
                match_date=pd.to_datetime(row.get('Date', datetime.now())))
            if pred:
                pred.league = row.get('League', '')
                predictions.append(pred)
        return predictions

    # ────────────────────────────────────────────
    # PERSISTENCE
    # ────────────────────────────────────────────

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        print(f"[Model] Saved to {path}")

    @classmethod
    def load(cls, path: Path) -> 'DixonColesModel':
        with open(path, 'rb') as f:
            model = pickle.load(f)
        print(f"[Model] Loaded from {path}")
        return model

"""
NBA Context Scraper
Holt Verletzungen, Load Management, Fatigue & Schedule Daten

Kritische NBA-Faktoren:
- Load Management (Stars sitzen aus)
- Back-to-Back Spiele (Fatigue)
- Rest Days (0, 1, 2+ Tage)
- Schedule Density (3-in-4, 4-in-5)
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pickle


class NBAContextScraper:
    """
    Vollständiger NBA Context mit:
    - Injuries
    - Load Management History
    - Back-to-Back Tracking
    - Rest Days Berechnung
    """
    
    # Star Spieler die oft Load Management bekommen
    LOAD_MANAGEMENT_STARS = {
        'LAL': ['LeBron James'],
        'LAC': ['Kawhi Leonard'],
        'PHX': ['Kevin Durant', 'Bradley Beal'],
        'MIL': ['Giannis Antetokounmpo'],
        'DEN': ['Jamal Murray'],
        'PHI': ['Joel Embiid'],
        'DAL': ['Kyrie Irving'],
        'NOP': ['Zion Williamson'],
    }
    
    # Position-Impact (Guard vs Center bei Fatigue)
    POSITION_FATIGUE_IMPACT = {
        'Guard': 0.8,     # Weniger betroffen
        'Forward': 1.0,   # Normal
        'Center': 1.2,    # Mehr betroffen (Physical)
    }
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/context")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache für Load Management Historie
        self.load_mgmt_cache = self.data_dir / "load_management_history.pkl"
        self.load_history = self._load_load_history()
        
        self.session = requests.Session()
        
    # ==== INJURY SCRAPING (aus injury_scraper.py übernommen) ====
    
    def fetch_injuries(self) -> List[Dict]:
        """Holt aktuelle Verletzte von ESPN"""
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            injuries = []
            for team_data in data.get('injuries', []):
                team = team_data.get('team', {}).get('abbreviation', '')
                
                for athlete in team_data.get('athletes', []):
                    athlete_data = athlete.get('athlete', {})
                    status = athlete.get('status', '')
                    
                    injuries.append({
                        'team': team,
                        'player': athlete_data.get('fullName', ''),
                        'status': status,
                        'is_out': self._is_out(status),
                        'is_doubtful': self._is_doubtful(status),
                        'is_load_mgmt': self._is_load_management(
                            athlete_data.get('fullName', ''), team, status
                        ),
                    })
            
            return injuries
            
        except Exception as e:
            print(f"[ContextScraper] Injuries Fehler: {e}")
            return []
    
    def _is_out(self, status: str) -> bool:
        """Definitiv out"""
        return any(word in status.lower() for word in ['out', 'injured reserve'])
    
    def _is_doubtful(self, status: str) -> bool:
        """Fraglich"""
        return any(word in status.lower() for word in ['doubtful', 'questionable', 'probable'])
    
    def _is_load_management(self, player: str, team: str, status: str) -> bool:
        """Load Management Erkennung"""
        # Prüfe ob Star-Spieler
        stars = self.LOAD_MANAGEMENT_STARS.get(team, [])
        is_star = any(star in player for star in stars)
        
        # Load Management Keywords
        load_mgmt_keywords = ['rest', 'maintenance', 'not injury related']
        
        return is_star and any(keyword in status.lower() for keyword in load_mgmt_keywords)
    
    # ==== LOAD MANAGEMENT TRACKING ====
    
    def _load_load_history(self) -> Dict:
        """Lädt Historie wer wann ausgesetzt hat"""
        if self.load_mgmt_cache.exists():
            with open(self.load_mgmt_cache, 'rb') as f:
                return pickle.load(f)
        return {}
    
    def _save_load_history(self):
        """Speichert Load Management Historie"""
        with open(self.load_mgmt_cache, 'wb') as f:
            pickle.dump(self.load_history, f)
    
    def track_load_management(self, player: str, team: str, date: str, reason: str):
        """Tracked Load Management Event"""
        key = f"{team}_{player}"
        
        if key not in self.load_history:
            self.load_history[key] = []
        
        self.load_history[key].append({
            'date': date,
            'reason': reason,
            'counted_in_last_10': True,  # Rolling window
        })
        
        # Speichern
        self._save_load_history()
    
    def get_load_mgmt_frequency(self, player: str, team: str, days: int = 30) -> Dict:
        """
        Berechnet wie oft ein Spieler Load Management bekam.
        
        Returns:
            {'count': int, 'frequency': float, 'trend': str}
        """
        key = f"{team}_{player}"
        events = self.load_history.get(key, [])
        
        # Filter letzte X Tage
        cutoff = datetime.now() - timedelta(days=days)
        recent = [e for e in events 
                  if datetime.fromisoformat(e['date']) > cutoff]
        
        count = len(recent)
        
        # Trend (steigend, fallend, stabil)
        if len(recent) >= 3:
            dates = [datetime.fromisoformat(e['date']) for e in recent[-3:]]
            gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            if avg_gap < 7:
                trend = 'high_freq'  # Sehr häufig
            elif avg_gap < 14:
                trend = 'moderate'
            else:
                trend = 'low'
        else:
            trend = 'unknown'
        
        return {
            'count': count,
            'frequency': count / days * 30,  # Pro Monat
            'trend': trend,
            'risk_level': 'high' if count >= 4 else ('medium' if count >= 2 else 'low')
        }
    
    # ==== BACK-TO-BACK & REST DAYS ====
    
    def calculate_fatigue(self, team: str, game_date: str, 
                          recent_games: List[Dict]) -> Dict:
        """
        Berechnet Fatigue Score basierend auf letzten Spielen.
        
        Args:
            recent_games: [{'date': '2026-03-15', 'home': bool, 'minutes': int}, ...]
        
        Returns:
            {
                'rest_days': int,           # Tage seit letztem Spiel
                'is_back_to_back': bool,    # 2 Spiele in 2 Tagen
                'is_3_in_4': bool,          # 3 Spiele in 4 Tagen
                'is_4_in_5': bool,          # 4 Spiele in 5 Tagen (worst)
                'fatigue_score': float,     # 0-100
                'travel_impact': float,     # Bonus für Fernreise
            }
        """
        if not recent_games:
            return {
                'rest_days': 3,  # Angenommen ausgeruht
                'is_back_to_back': False,
                'is_3_in_4': False,
                'is_4_in_5': False,
                'fatigue_score': 0,
                'travel_impact': 0,
                'total_impact': 0  # FIX: Fehlender Key!
            }
        
        # Sortiere nach Datum
        games = sorted(recent_games, key=lambda x: x['date'], reverse=True)
        
        # Rest Days
        last_game = datetime.fromisoformat(games[0]['date'])
        game_dt = datetime.fromisoformat(game_date)
        rest_days = (game_dt - last_game).days
        
        # Back-to-Back Detection
        is_b2b = rest_days == 0
        
        # 3-in-4 und 4-in-5 Detection
        if len(games) >= 3:
            dates = [datetime.fromisoformat(g['date']) for g in games[:4]]
            date_diffs = [(dates[i] - dates[i+1]).days for i in range(len(dates)-1)]
            
            is_3_in_4 = len([d for d in date_diffs[:2] if d <= 1]) >= 2
            is_4_in_5 = len([d for d in date_diffs[:3] if d <= 1]) >= 3
        else:
            is_3_in_4 = False
            is_4_in_5 = False
        
        # Fatigue Score berechnen
        fatigue_score = 0
        if is_4_in_5:
            fatigue_score = 85
        elif is_3_in_4:
            fatigue_score = 60
        elif is_b2b:
            fatigue_score = 40
        elif rest_days == 1:
            fatigue_score = 25
        elif rest_days == 2:
            fatigue_score = 10
        else:
            fatigue_score = 0
        
        # Travel Impact (West Coast -> East Coast = schlimm)
        travel_impact = 0
        if len(games) > 0:
            last_game = games[0]
            if last_game.get('home', True) != False:  # War auf Reisen
                travel_distance = last_game.get('travel_distance', 0)
                if travel_distance > 2000:  # Cross-country
                    travel_impact = 15
                elif travel_distance > 1000:
                    travel_impact = 8
        
        return {
            'rest_days': rest_days,
            'is_back_to_back': is_b2b,
            'is_3_in_4': is_3_in_4,
            'is_4_in_5': is_4_in_5,
            'fatigue_score': fatigue_score,
            'travel_impact': travel_impact,
            'total_impact': min(fatigue_score + travel_impact, 100)
        }
    
    # ==== TEAM CONTEXT ZUSAMMENFASSUNG ====
    
    def get_team_context(self, team: str, game_date: str, 
                         recent_games: List[Dict] = None) -> Dict:
        """
        Holt kompletten Context für ein Team.
        
        Returns:
            {
                'injuries': {'out': int, 'doubtful': int, 'load_mgmt': int},
                'fatigue': {},
                'load_mgmt_risk': str,
                'context_summary': str
            }
        """
        # Injuries
        injuries = self.fetch_injuries()
        team_inj = [i for i in injuries if i['team'] == team]
        
        injury_summary = {
            'total_out': sum(1 for i in team_inj if i['is_out']),
            'doubtful': sum(1 for i in team_inj if i['is_doubtful']),
            'load_mgmt': sum(1 for i in team_inj if i['is_load_mgmt']),
            'key_injuries': [i for i in team_inj 
                           if i['is_out'] and any(
                               star in i['player'] 
                               for star in self.LOAD_MANAGEMENT_STARS.get(team, [])
                           )]
        }
        
        # Fatigue
        fatigue = self.calculate_fatigue(team, game_date, recent_games or [])
        
        # Load Management Risk
        load_risk = 'low'
        for player in self.LOAD_MANAGEMENT_STARS.get(team, []):
            freq = self.get_load_mgmt_frequency(player, team)
            if freq['risk_level'] == 'high':
                load_risk = 'high'
                break
            elif freq['risk_level'] == 'medium' and load_risk == 'low':
                load_risk = 'medium'
        
        # Context Rating
        context_rating = 100
        context_rating -= fatigue['total_impact']
        context_rating -= injury_summary['total_out'] * 10
        context_rating -= injury_summary['doubtful'] * 5
        context_rating -= injury_summary['load_mgmt'] * 15
        context_rating = max(0, context_rating)
        
        return {
            'team': team,
            'injuries': injury_summary,
            'fatigue': fatigue,
            'load_mgmt_risk': load_risk,
            'context_rating': context_rating,
            'context_summary': self._format_summary(team, injury_summary, fatigue, load_risk)
        }
    
    def _format_summary(self, team: str, injuries: Dict, fatigue: Dict, load_risk: str) -> str:
        """Erzeugt lesbare Zusammenfassung"""
        lines = [f"📊 {team} Context:"]
        
        if fatigue['is_4_in_5']:
            lines.append("  ⚠️  4 Spiele in 5 Tagen (extreme fatigue)")
        elif fatigue['is_3_in_4']:
            lines.append(f"  ⚠️  3 in 4 + B2B ({fatigue['rest_days']} Tage Rest)")
        elif fatigue['is_back_to_back']:
            lines.append("  😰 Back-to-Back Spiel")
        elif fatigue['rest_days'] >= 2:
            lines.append(f"  ✅ Optimal: {fatigue['rest_days']} Tage Rest")
        
        if injuries['total_out'] > 0:
            star_out = len([p for p in injuries['key_injuries']])
            if star_out > 0:
                lines.append(f"  🚑 {star_out} Star-Spieler OUT")
            else:
                lines.append(f"  ⚡ {injuries['total_out']} Spieler aus")
        
        if injuries['load_mgmt'] > 0:
            lines.append(f"  😴 {injuries['load_mgmt']} Load Management")
        
        if load_risk == 'high':
            lines.append("  ⚠️  Hohes Load-Management Risiko")
        
        return "\n".join(lines)
    
    def get_match_context(self, home_team: str, away_team: str, 
                          game_date: str) -> Dict:
        """Holt Context für beide Teams"""
        home = self.get_team_context(home_team, game_date)
        away = self.get_team_context(away_team, game_date)
        
        return {
            'home': home,
            'away': away,
            'context_diff': home['context_rating'] - away['context_rating'],
            'warning_level': self._determine_warning_level(home, away)
        }
    
    def _determine_warning_level(self, home: Dict, away: Dict) -> str:
        """Bestimmt wie sehr Context die Vorhersage verfälscht"""
        level = 'low'
        
        # Hohe Fatigue
        if (home['fatigue']['is_4_in_5'] or away['fatigue']['is_4_in_5'] or
            home['fatigue']['total_impact'] > 50 or away['fatigue']['total_impact'] > 50):
            level = 'high'
        # Star-Spieler out
        elif (home['injuries']['key_injuries'] or away['injuries']['key_injuries']):
            level = 'high'
        # Moderate issues
        elif (home['fatigue']['is_3_in_4'] or away['fatigue']['is_3_in_4'] or
              home['injuries']['total_out'] >= 2 or away['injuries']['total_out'] >= 2):
            level = 'medium'
        
        return level


# Globaler Scraper
context_scraper = NBAContextScraper()


if __name__ == "__main__":
    print("[NBA Context Scraper] Test-Modus")
    
    s = NBAContextScraper()
    
    # Test: Lakers Context
    print("\n=== Lakers Context (heute) ===")
    context = s.get_team_context('LAL', datetime.now().isoformat()[:10])
    print(context['context_summary'])
    print(f"\nContext Rating: {context['context_rating']}/100")
    print(f"Load Mgmt Risk: {context['load_mgmt_risk']}")
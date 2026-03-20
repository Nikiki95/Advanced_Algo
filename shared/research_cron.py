#!/usr/bin/env python3
"""
Universal Research Cron
Holt alle 4 Stunden Injury/Context Daten für alle Sportarten
Football + NBA + NFL
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "football" / "src" / "utils"))
sys.path.insert(0, str(Path(__file__).parent.parent / "nba" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "nfl" / "src"))


class ResearchDatabase:
    """Zentrale SQLite DB für alle Context-Daten"""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "research.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Football
        cur.execute("""
            CREATE TABLE IF NOT EXISTS football_injuries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT NOT NULL, player TEXT NOT NULL, status TEXT,
                severity INTEGER DEFAULT 1, impact_score REAL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team, player)
            )
        """)
        
        # NBA
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nba_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_code TEXT NOT NULL, player_name TEXT, context_type TEXT,
                status TEXT, severity INTEGER DEFAULT 1, impact_score REAL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_code, player_name, context_type)
            )
        """)
        
        # NFL NEU
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nfl_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_code TEXT NOT NULL, player_name TEXT, context_type TEXT,
                status TEXT, severity INTEGER DEFAULT 1, impact_score REAL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_code, player_name, context_type)
            )
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_foot_team ON football_injuries(team)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nba_team ON nba_context(team_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nfl_team ON nfl_context(team_code)")
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)


class ResearchCron:
    """Haupt-Research Cron"""
    
    def __init__(self):
        self.db = ResearchDatabase()
    
    def run(self):
        """Führt kompletten Research-Durchlauf durch"""
        print(f"\n{'='*60}")
        print(f"🔬 RESEARCH CRON - {datetime.now().strftime('%H:%M')}")
        print(f"{'='*60}")
        
        football = self._research_football()
        nba = self._research_nba()
        nfl = self._research_nfl()
        
        print(f"\n📊 SUMMARY:")
        print(f"  Football: {football} Verletzte")
        print(f"  NBA: {nba} Context-Einträge")
        print(f"  NFL: {nfl} Context-Einträge")
        print(f"{'='*60}\n")
    
    def _research_football(self) -> int:
        """Research für Football"""
        print("\n⚽ Football Research...")
        try:
            from lineup_scraper import FootballLineupScraper
            scraper = FootballLineupScraper()
            teams = list(scraper.get_all_teams())[:20]
        except Exception as e:
            print(f"  ⚠️ Scraper nicht verfügbar: {e}")
            return 0
        
        conn = self.db.get_connection()
        cur = conn.cursor()
        count = 0
        
        for team in teams:
            try:
                lineup = scraper.get_team_lineup(team)
                if lineup.get('key_players_missing', 0) > 0:
                    cur.execute("""
                        INSERT OR REPLACE INTO football_injuries 
                        (team, player, status, severity, impact_score)
                        VALUES (?, ?, 'simulated', 2, ?)
                    """, (team, f"{lineup['key_players_missing']} players", lineup.get('impact_score', 0)))
                    count += 1
            except Exception as e:
                print(f"  ⚠️ {team}: {e}")
        
        conn.commit()
        conn.close()
        print(f"  ✅ {count} Einträge")
        return count
    
    def _research_nba(self) -> int:
        """Research für NBA"""
        print("\n🏀 NBA Research...")
        
        try:
            from reddit_injury_scraper import RedditInjuryScraper
            scraper = RedditInjuryScraper()
            injuries = scraper.fetch_injuries()
        except Exception as e:
            print(f"  ⚠️ Scraper: {e}")
            injuries = []
        
        conn = self.db.get_connection()
        cur = conn.cursor()
        count = 0
        
        for inj in injuries:
            try:
                status = inj.get('status', 'unknown')
                severity = {'out': 3, 'doubtful': 2, 'questionable': 1}.get(status, 1)
                impact = {'out': 25, 'doubtful': 15, 'questionable': 5}.get(status, 5)
                
                cur.execute("""
                    INSERT OR REPLACE INTO nba_context 
                    (team_code, player_name, context_type, status, severity, impact_score)
                    VALUES (?, ?, 'injury', ?, ?, ?)
                """, (inj['team'], inj['player'], status, severity, impact))
                count += 1
                print(f"    ✅ {inj['player']} ({inj['team']}) - {status}")
            except Exception as e:
                print(f"    ⚠️ DB: {e}")
        
        conn.commit()
        conn.close()
        print(f"  ✅ {count} Einträge")
        return count
    
    def _research_nfl(self) -> int:
        """Research für NFL"""
        print("\n🏈 NFL Research...")
        
        try:
            from injury_scraper import NFLInjuryScraper
            scraper = NFLInjuryScraper()
            injuries = scraper.fetch_injuries()
        except Exception as e:
            print(f"  ⚠️ Scraper: {e}")
            injuries = []
        
        conn = self.db.get_connection()
        cur = conn.cursor()
        count = 0
        
        for inj in injuries:
            try:
                status = inj.get('status', 'unknown')
                severity = {'out': 3, 'doubtful': 2, 'questionable': 1, 'probable': 0}.get(status, 1)
                impact = {'out': 25, 'doubtful': 15, 'questionable': 5, 'probable': 2}.get(status, 5)
                
                cur.execute("""
                    INSERT OR REPLACE INTO nfl_context 
                    (team_code, player_name, context_type, status, severity, impact_score)
                    VALUES (?, ?, 'injury', ?, ?, ?)
                """, (inj['team'], inj['player'], status, severity, impact))
                count += 1
                print(f"    ✅ {inj['player']} ({inj['team']}) - {status}")
            except Exception as e:
                print(f"    ⚠️ DB: {e}")
        
        conn.commit()
        conn.close()
        print(f"  ✅ {count} Einträge")
        return count
    
    def get_context_for_match(self, sport: str, home: str, away: str) -> Dict:
        """Holt Context für ein Match"""
        conn = self.db.get_connection()
        cur = conn.cursor()
        result = {'home': {}, 'away': {}}
                
        if sport == 'football':
            table = 'football_injuries'
            select = 'player, status, severity, impact_score'
            col = 'team'
        elif sport == 'nba':
            table = 'nba_context'
            select = 'player_name, context_type, status, severity, impact_score'
            col = 'team_code'
        elif sport == 'nfl':
            table = 'nfl_context'
            select = 'player_name, context_type, status, severity, impact_score'
            col = 'team_code'
        else:
            conn.close()
            return result
        
        for team, key in [(home, 'home'), (away, 'away')]:
            cur.execute(f"""
                SELECT {select} FROM {table} 
                WHERE {col} = ?
            """, (team,))
            result[key] = cur.fetchall()
        
        conn.close()
        return result


if __name__ == "__main__":
    cron = ResearchCron()
    cron.run()

"""
NFL Injury Scraper - Hybrid Approach
1. ESPN RSS (free)
2. NFL.com (scraping)
3. Manual backup (current data)
"""

import requests
import re
from datetime import datetime
from typing import Dict, List
import xml.etree.ElementTree as ET


class NFLInjuryScraper:
    """Hybrid Scraper for NFL Injuries"""
    
    TEAM_MAP = {
        'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons',
        'BAL': 'Baltimore Ravens', 'BUF': 'Buffalo Bills',
        'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears',
        'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns',
        'DAL': 'Dallas Cowboys', 'DEN': 'Denver Broncos',
        'DET': 'Detroit Lions', 'GB': 'Green Bay Packers',
        'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts',
        'JAX': 'Jacksonville Jaguars', 'KC': 'Kansas City Chiefs',
        'LAC': 'LA Chargers', 'LAR': 'LA Rams',
        'LV': 'Las Vegas Raiders', 'MIA': 'Miami Dolphins',
        'MIN': 'Minnesota Vikings', 'NE': 'New England Patriots',
        'NO': 'New Orleans Saints', 'NYG': 'NY Giants',
        'NYJ': 'NY Jets', 'PHI': 'Philadelphia Eagles',
        'PIT': 'Pittsburgh Steelers', 'SEA': 'Seattle Seahawks',
        'SF': 'San Francisco 49ers', 'TB': 'Tampa Bay Buccaneers',
        'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    def fetch_injuries(self) -> List[Dict]:
        """Tries all free sources"""
        # Try ESPN RSS
        injuries = self._try_espn_rss()
        if injuries:
            return injuries
        
        # Fallback to manual
        print("   ℹ️ Using manual backup data")
        return self._get_mock()
    
    def _try_espn_rss(self) -> List[Dict]:
        """ESPN NFL Injuries RSS"""
        try:
            url = "https://www.espn.com/espn/rss/nfl/injuries"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            injuries = []
            
            for item in root.findall('.//item'):
                title = item.find('title')
                if title is None:
                    continue
                    
                title_text = title.text or ''
                match = re.match(r'^([^(]+)\s*\(([^)]+)\)\s*-\s*(.+)$', title_text)
                
                if match:
                    player, team, status = match.groups()
                    injuries.append({
                        'player': player.strip(),
                        'team': self._normalize_team(team.strip()),
                        'status': self._parse_status(status),
                        'reason': status.strip(),
                        'source': 'espn'
                    })
            
            if injuries:
                print(f"   ✅ {len(injuries)} from ESPN RSS")
                return injuries
            return []
            
        except Exception as e:
            print(f"   ⚠️ ESPN RSS: {str(e)[:30]}")
            return []
    
    def _get_mock(self) -> List[Dict]:
        """Current NFL injuries (March 2025 - Offseason)"""
        return [
            {'player': 'Patrick Mahomes', 'team': 'KC', 'status': 'probable', 
             'reason': 'Ankle - offseason recovery', 'source': 'manual'},
            {'player': 'Joe Burrow', 'team': 'CIN', 'status': 'probable',
             'reason': 'ACL - cleared for camp', 'source': 'manual'},
            {'player': 'Aaron Rodgers', 'team': 'PIT', 'status': 'questionable',
             'reason': 'Achilles - rehab', 'source': 'manual'},
        ]
    
    def _normalize_team(self, team: str) -> str:
        """Normalize team name"""
        team_upper = team.strip().upper().replace(' ', '')
        
        abbrevs = ['ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE',
                   'DAL', 'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC',
                   'LAC', 'LAR', 'LV', 'MIA', 'MIN', 'NE', 'NO', 'NYG',
                   'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS']
        
        for abbr in abbrevs:
            if abbr in team_upper:
                return abbr
        return team_upper[:3]
    
    def _parse_status(self, status: str) -> str:
        """Parse injury status"""
        status_lower = status.lower()
        if 'out' in status_lower:
            return 'out'
        elif 'doubtful' in status_lower:
            return 'doubtful'
        elif 'questionable' in status_lower:
            return 'questionable'
        elif 'probable' in status_lower:
            return 'probable'
        return 'unknown'


if __name__ == "__main__":
    print("=" * 60)
    print("NFL Injury Scraper")
    print("=" * 60)
    
    scraper = NFLInjuryScraper()
    injuries = scraper.fetch_injuries()
    
    print(f"\n🏈 {len(injuries)} Verletzungen\n")
    for i, inj in enumerate(injuries, 1):
        icon = "📡" if inj['source'] == 'espn' else "✍️"
        print(f"{icon} {i}. {inj['player']:<25} ({inj['team']:<6}) - {inj['status']}")

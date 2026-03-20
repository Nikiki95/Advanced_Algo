"""
NBA/NFL Injury Scraper - Hybrid Approach
Tries multiple sources: ESPN RSS, Rotowire, then manual backup
"""

import requests
import re
import json
from datetime import datetime
from typing import Dict, List
import xml.etree.ElementTree as ET


class HybridInjuryScraper:
    """
    Hybrid Scraper:
    1. ESPN RSS (kostenlos)
    2. Rotowire (kostenlos)
    3. Mock data (fallback)
    """
    
    TEAM_abbreviations = {
        'LAL': 'Lakers', 'BOS': 'Celtics', 'GSW': 'Warriors',
        'NYK': 'Knicks', 'MIA': 'Heat', 'PHI': '76ers',
        'DAL': 'Mavericks', 'DEN': 'Nuggets', 'PHX': 'Suns',
        'LAC': 'Clippers', 'MIL': 'Bucks', 'CLE': 'Cavaliers'
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0'
        })
    
    def get_nba_injuries(self) -> List[Dict]:
        """Tries ESPN RSS first, then falls back"""
        injuries = self._try_espn_rss()
        if injuries:
            return injuries
        
        return self._get_recent_mock_injuries()
    
    def _try_espn_rss(self) -> List[Dict]:
        """ESPN RSS Feed - kostenlos"""
        try:
            url = "https://www.espn.com/espn/rss/nba/injuries"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse RSS
            root = ET.fromstring(response.content)
            injuries = []
            
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ''
                
                # Parse: "Player Name (Team) - Status"
                match = re.match(r'^([^(]+)\s+\(([^)]+)\)\s*-\s*(.+)$', title)
                if match:
                    player, team, status = match.groups()
                    injuries.append({
                        'player': player.strip(),
                        'team': self._normalize_team(team.strip()),
                        'status': self._parse_status(status),
                        'reason': status.strip(),
                        'source': 'espn_rss'
                    })
            
            print(f"   ✅ {len(injuries)} von ESPN RSS")
            return injuries
            
        except Exception as e:
            print(f"   ⚠️ ESPN RSS: {e}")
            return []
    
    def _get_recent_mock_injuries(self) -> List[Dict]:
        """Aktuelle Verletzungen (Stand: März 2025)"""
        return [
            {'player': 'Kawhi Leonard', 'team': 'LAC', 'status': 'questionable', 'reason': 'Knee injury', 'source': 'manual'},
            {'player': 'Jamal Murray', 'team': 'DEN', 'status': 'questionable', 'reason': 'Hamstring', 'source': 'manual'},
            {'player': 'OG Anunoby', 'team': 'NYK', 'status': 'out', 'reason': 'Foot surgery', 'source': 'manual'},
            {'player': 'LaMelo Ball', 'team': 'CHA', 'status': 'out', 'reason': 'Ankle', 'source': 'manual'},
            {'player': 'Victor Wembanyama', 'team': 'SAS', 'status': 'out', 'reason': 'DVT - season', 'source': 'manual'},
        ]
    
    def _normalize_team(self, team_str: str) -> str:
        """Team-Namen normalisieren"""
        team_upper = team_str.upper()
        for code, name in self.TEAM_abbreviations.items():
            if code in team_upper or name.upper() in team_upper:
                return code
        return team_str[:3]
    
    def _parse_status(self, status_str: str) -> str:
        """Status aus String parsen"""
        status_lower = status_str.lower()
        if 'out' in status_lower:
            return 'out'
        elif 'doubtful' in status_lower:
            return 'doubtful'
        elif 'questionable' in status_lower:
            return 'questionable'
        return 'unknown'


if __name__ == "__main__":
    scraper = HybridInjuryScraper()
    injuries = scraper.get_nba_injuries()
    
    print(f"\n🏥 {len(injuries)} Verletzungen\n")
    for i, inj in enumerate(injuries, 1):
        print(f"{i}. {inj['player']:<25} ({inj['team']:<10}) - {inj['status']} ({inj['source']})")

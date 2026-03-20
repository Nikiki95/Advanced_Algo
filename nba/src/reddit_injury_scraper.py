"""
NBA Injury Scraper - Hybrid Approach
1. Reddit r/fantasybball (kostenlos)
2. ESPN RSS Feed (kostenlos)
3. Manual Backup (aktuelle Daten)

All sources are free and reliable.
"""

import requests
import re
from datetime import datetime
from typing import Dict, List
import xml.etree.ElementTree as ET


class RedditInjuryScraper:
    """Hybrid Scraper for NBA Injuries - Free sources only"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (BettingBot/1.0)'
        })
    
    def fetch_injuries(self) -> List[Dict]:
        """Tries all free sources in order"""
        # Try Reddit
        injuries = self._try_reddit()
        if injuries:
            return injuries
        
        # Try ESPN RSS
        injuries = self._try_espn_rss()
        if injuries:
            return injuries
        
        # Fallback to manual data
        print("   ℹ️ Using manual backup data")
        return self._get_mock()
    
    def _try_reddit(self) -> List[Dict]:
        """r/fantasybball"""
        try:
            url = "https://www.reddit.com/r/fantasybball/search.json"
            params = {'q': 'injury report', 'restrict_sr': 'true', 'sort': 'new', 't': 'day', 'limit': 5}
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            injuries = []
            for post in data.get('data', {}).get('children', []):
                text = post.get('data', {}).get('selftext', '')
                for line in text.split('\n'):
                    match = re.search(
                        r'([A-Z][a-z]+\s+[A-Z][a-z]+).*?\((\w+)\).*?\b(out|questionable|doubtful)',
                        line, re.IGNORECASE
                    )
                    if match:
                        player, team, status = match.groups()
                        injuries.append({
                            'player': player.strip(),
                            'team': self._normalize_team(team),
                            'status': status.lower(),
                            'reason': 'From Reddit',
                            'source': 'reddit'
                        })
            
            if injuries:
                print(f"   ✅ {len(injuries)} from Reddit")
                return injuries
            return []
            
        except Exception as e:
            print(f"   ⚠️ Reddit: {str(e)[:30]}")
            return []
    
    def _try_espn_rss(self) -> List[Dict]:
        """ESPN NBA Injuries RSS"""
        try:
            url = "https://www.espn.com/espn/rss/nba/injuries"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            injuries = []
            
            for item in root.findall('.//item'):
                title = item.find('title')
                if title is None:
                    continue
                title_text = title.text or ''
                
                # Parse: "Player Name (Team) - Status"
                match = re.match(r'^([^(]+)\s+\(([^)]+)\)\s*-\s*(.+)$', title_text)
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
        """Current injuries as of March 2025"""
        return [
            {'player': 'Victor Wembanyama', 'team': 'SAS', 'status': 'out', 'reason': 'Deep vein thrombosis - season', 'source': 'manual'},
            {'player': 'OG Anunoby', 'team': 'NYK', 'status': 'out', 'reason': 'Foot surgery', 'source': 'manual'},
            {'player': 'Jalen Suggs', 'team': 'ORL', 'status': 'out', 'reason': 'Knee surgery - season', 'source': 'manual'},
            {'player': 'Markelle Fultz', 'team': 'ORL', 'status': 'out', 'reason': 'Knee injury', 'source': 'manual'},
            {'player': 'Kawhi Leonard', 'team': 'LAC', 'status': 'questionable', 'reason': 'Knee management', 'source': 'manual'},
            {'player': 'Jamal Murray', 'team': 'DEN', 'status': 'questionable', 'reason': 'Hamstring tightness', 'source': 'manual'},
            {'player': 'LaMelo Ball', 'team': 'CHA', 'status': 'out', 'reason': 'Ankle sprain', 'source': 'manual'},
        ]
    
    def _normalize_team(self, team: str) -> str:
        """Normalize team abbreviations"""
        team_map = {
            'LAL': 'LAL', 'LAKERS': 'LAL', 'LOS ANGELES LAKERS': 'LAL',
            'BOS': 'BOS', 'CELTICS': 'BOS', 'BOSTON': 'BOS',
            'GSW': 'GSW', 'WARRIORS': 'GSW', 'GOLDEN STATE': 'GSW',
            'NYK': 'NYK', 'KNICKS': 'NYK', 'NEW YORK': 'NYK',
            'MIA': 'MIA', 'HEAT': 'MIA', 'MIAMI': 'MIA',
            'PHI': 'PHI', '76ERS': 'PHI', 'PHILADELPHIA': 'PHI',
            'DAL': 'DAL', 'MAVERICKS': 'DAL', 'DALLAS': 'DAL',
            'DEN': 'DEN', 'NUGGETS': 'DEN', 'DENVER': 'DEN',
            'PHX': 'PHX', 'SUNS': 'PHX', 'PHOENIX': 'PHX',
            'LAC': 'LAC', 'CLIPPERS': 'LAC', 'LA CLIPPERS': 'LAC',
            'MIL': 'MIL', 'BUCKS': 'MIL', 'MILWAUKEE': 'MIL',
            'CLE': 'CLE', 'CAVALIERS': 'CLE', 'CLEVELAND': 'CLE',
            'SAS': 'SAS', 'SPURS': 'SAS', 'SAN ANTONIO': 'SAS',
            'CHA': 'CHA', 'HORNETS': 'CHA', 'CHARLOTTE': 'CHA',
            'ORL': 'ORL', 'MAGIC': 'ORL', 'ORLANDO': 'ORL',
        }
        team_upper = team.strip().upper()
        return team_map.get(team_upper, team_upper[:3])
    
    def _parse_status(self, status: str) -> str:
        """Parse status from text"""
        status_lower = status.lower()
        if 'out' in status_lower or 'suspended' in status_lower:
            return 'out'
        elif 'doubtful' in status_lower:
            return 'doubtful'
        elif 'questionable' in status_lower:
            return 'questionable'
        return 'unknown'


if __name__ == "__main__":
    print("=" * 60)
    print("NBA Hybrid Injury Scraper")
    print("=" * 60)
    
    scraper = RedditInjuryScraper()
    injuries = scraper.fetch_injuries()
    
    print(f"\n🏥 {len(injuries)} Verletzungen\n")
    for i, inj in enumerate(injuries, 1):
        source_icon = "📡" if inj['source'] in ['reddit', 'espn'] else "✍️"
        print(f"{source_icon} {i}. {inj['player']:<25} ({inj['team']:<10}) - {inj['status']}")

"""
API-Sports Client für Injuries
NBA, NFL, Football (Soccer)
Kostenlos: 100 Calls/Tag
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class APISportsClient:
    """
    Client für API-Sports (v3.football, v2.nba, v1.american-football)
    kostenlos: 100 Requests/Tag pro Sport
    """
    
    BASE_URLS = {
        'football': 'https://v3.football.api-sports.io',
        'nba': 'https://v2.nba.api-sports.io',
        'nfl': 'https://v1.american-football.api-sports.io'
    }
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._load_key()
        self.session = requests.Session()
        self.session.headers.update({
            'x-apisports-key': self.api_key
        })
    
    def _load_key(self) -> str:
        """Lädt API-Key aus .env"""
        env_path = Path(__file__).parent.parent / "secrets" / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if 'APISPORTS_KEY' in line:
                        return line.split('=', 1)[1].strip()
        return None
    

    def request(self, sport: str, path: str, params: Dict = None) -> Dict:
        """Generic request helper for API-Sports endpoints."""
        if not self.api_key:
            return {}
        base = self.BASE_URLS.get(sport)
        if not base:
            return {}
        url = f"{base}{path}"
        try:
            response = self.session.get(url, params=params or {}, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

    def get_nba_injuries(self) -> List[Dict]:
        """Holt NBA Verletzungen"""
        url = f"{self.BASE_URLS['nba']}/players"
        params = {'season': '2025', 'injured': 'true', 'league': 'standard'}
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            injuries = []
            for player in data.get('response', []):
                inj = player.get('injury', {})
                if inj:
                    injuries.append({
                        'player': f"{player.get('firstname', '')} {player.get('lastname', '')}".strip(),
                        'team': player.get('team', {}).get('name', ''),
                        'team_code': player.get('team', {}).get('code', ''),
                        'status': inj.get('status', 'unknown'),  # Active, Day To Day, Out
                        'type': inj.get('type', ''),
                        'description': inj.get('description', ''),
                        'source': 'api-sports',
                        'fetched_at': datetime.now().isoformat()
                    })
            
            print(f"   ✅ {len(injuries)} NBA Verletzungen von API-Sports")
            return injuries
            
        except Exception as e:
            print(f"   ⚠️ NBA API Error: {e}")
            return []
    
    def get_nfl_injuries(self) -> List[Dict]:
        """Holt NFL Verletzungen"""
        url = f"{self.BASE_URLS['nfl']}/injuries"
        params = {'season': '2025', 'league': '1'}
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            injuries = []
            for inj in data.get('response', []):
                injuries.append({
                    'player': inj.get('player', {}).get('name', ''),
                    'team': inj.get('team', {}).get('name', ''),
                    'position': inj.get('player', {}).get('position', ''),
                    'status': inj.get('status', 'unknown'),  # Questionable, Doubtful, Out, etc.
                    'type': inj.get('type', ''),
                    'description': inj.get('comment', ''),
                    'source': 'api-sports',
                    'fetched_at': datetime.now().isoformat()
                })
            
            print(f"   ✅ {len(injuries)} NFL Verletzungen von API-Sports")
            return injuries
            
        except Exception as e:
            print(f"   ⚠️ NFL API Error: {e}")
            return []
    
    def get_football_injuries(self, league: str, season: str = '2025') -> List[Dict]:
        """Holt Football (Soccer) Verletzungen"""
        url = f"{self.BASE_URLS['football']}/injuries"
        params = {'league': league, 'season': season}
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            injuries = []
            for inj in data.get('response', []):
                injuries.append({
                    'player': inj.get('player', {}).get('name', ''),
                    'team': inj.get('team', {}).get('name', ''),
                    'fixture': inj.get('fixture', {}).get('id', ''),
                    'type': inj.get('type', ''),
                    'reason': inj.get('reason', ''),
                    'source': 'api-sports',
                    'fetched_at': datetime.now().isoformat()
                })
            
            print(f"   ✅ {len(injuries)} Football Verletzungen (League {league})")
            return injuries
            
        except Exception as e:
            print(f"   ⚠️ Football API Error: {e}")
            return []


if __name__ == "__main__":
    print("=" * 60)
    print("API-Sports Client - Test")
    print("=" * 60)
    
    client = APISportsClient()
    
    print("\n🏀 NBA Injuries:")
    nba = client.get_nba_injuries()
    for inj in nba[:5]:
        print(f"  {inj['player']:<25} ({inj['team']:<20}) - {inj['status']}")
    
    print("\n🏈 NFL Injuries:")
    nfl = client.get_nfl_injuries()
    for inj in nfl[:3]:
        print(f"  {inj['player']:<25} ({inj['team']:<20}) - {inj['status']}")

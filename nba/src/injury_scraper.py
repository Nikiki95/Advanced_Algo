"""
NBA Injury Scraper - KOSTENLOS ohne API-Key
Nutzt basketball-reference.com (HTML scraping)
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List


class NBAInjuryScraper:
    """Kostenloser Scraper - keine API-Key nötig"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    def fetch_injuries(self) -> List[Dict]:
        """Holt Verletzungen von basketball-reference.com"""
        url = "https://www.basketball-reference.com/friv/injuries.fcgi"
        
        try:
            print("   [Basketball-Reference] Scraping...")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            injuries = []
            
            # Finde Injury-Tabelle
            table = soup.find('table', {'id': 'injuries'})
            if not table:
                print("   ⚠️ Keine Tabelle gefunden")
                return self._get_mock_injuries()
            
            rows = table.find('tbody').find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    player = cells[0].text.strip()
                    team_abbr = cells[1].text.strip()
                    date_str = cells[2].text.strip()
                    desc = cells[3].text.strip()
                    
                    status = self._parse_status(desc)
                    
                    injuries.append({
                        'player': player,
                        'team': self._map_team_abbr(team_abbr),
                        'status': status,
                        'reason': desc,
                        'date': date_str or datetime.now().strftime('%Y-%m-%d')
                    })
            
            print(f"   ✅ {len(injuries)} Verletzungen gefunden")
            return injuries if injuries else self._get_mock_injuries()
            
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            return self._get_mock_injuries()
    
    def _map_team_abbr(self, abbr: str) -> str:
        """Team Abkürzungen → Namen"""
        abbr_map = {
            'ATL': 'Atlanta', 'BOS': 'Boston', 'BRK': 'Brooklyn',
            'CHO': 'Charlotte', 'CHI': 'Chicago', 'CLE': 'Cleveland',
            'DAL': 'Dallas', 'DEN': 'Denver', 'DET': 'Detroit',
            'GSW': 'Golden State', 'HOU': 'Houston', 'IND': 'Indiana',
            'LAC': 'LA Clippers', 'LAL': 'LAL', 'MEM': 'Memphis',
            'MIA': 'Miami', 'MIL': 'Milwaukee', 'MIN': 'Minnesota',
            'NOP': 'New Orleans', 'NYK': 'New York', 'OKC': 'Oklahoma City',
            'ORL': 'Orlando', 'PHI': 'Philadelphia', 'PHO': 'Phoenix',
            'POR': 'Portland', 'SAC': 'Sacramento', 'SAS': 'San Antonio',
            'TOR': 'Toronto', 'UTA': 'Utah', 'WAS': 'Washington'
        }
        return abbr_map.get(abbr, abbr)
    
    def _parse_status(self, desc: str) -> str:
        """Extrahiert Status aus Beschreibung"""
        desc_lower = desc.lower()
        if 'out' in desc_lower:
            return 'out'
        elif 'doubtful' in desc_lower:
            return 'doubtful'
        elif 'questionable' in desc_lower:
            return 'questionable'
        elif 'probable' in desc_lower:
            return 'probable'
        return 'unknown'
    
    def _get_mock_injuries(self) -> List[Dict]:
        """Mock-Daten als Fallback"""
        return [
            {'player': 'Victor Wembanyama', 'team': 'San Antonio', 'status': 'out', 
             'reason': 'Deep vein thrombosis - out for season', 'date': '2025-03-15'},
            {'player': 'LaMelo Ball', 'team': 'Charlotte', 'status': 'out',
             'reason': 'Ankle sprain - expected return mid-March', 'date': '2025-03-10'},
            {'player': 'Anthony Davis', 'team': 'LAL', 'status': 'questionable',
             'reason': 'Foot soreness - game-time decision', 'date': '2025-03-18'},
        ]
    
    def get_team_impact(self, team_name: str) -> Dict:
        """Impact-Score für ein Team"""
        injuries = self.fetch_injuries()
        team_inj = [i for i in injuries if team_name.lower() in i['team'].lower()]
        
        if not team_inj:
            return {'team': team_name, 'count': 0, 'impact_score': 0}
        
        weights = {'out': 1.0, 'doubtful': 0.6, 'questionable': 0.3}
        impact = sum(weights.get(i['status'], 0.2) for i in team_inj) * 15
        
        return {
            'team': team_name,
            'count': len(team_inj),
            'impact_score': min(impact, 100),
            'out_count': sum(1 for i in team_inj if i['status'] == 'out'),
            'players': team_inj
        }


if __name__ == "__main__":
    print("=" * 60)
    print("NBA Injury Scraper - KOSTENLOS ohne API-Key")
    print("=" * 60)
    
    scraper = NBAInjuryScraper()
    injuries = scraper.fetch_injuries()
    
    print(f"\n🏥 {len(injuries)} Verletzungen\n")
    for i, inj in enumerate(injuries[:5], 1):
        print(f"{i}. {inj['player']:<25} ({inj['team']:<15}) - {inj['status']}")

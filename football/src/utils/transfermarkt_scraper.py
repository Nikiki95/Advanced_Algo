"""
Transfermarkt Scraper - VERLETZTE & AUFSTELLUNGEN

⚠️ WARNUNG: Transfermarkt hat Cloudflare-Schutz!
- Playwright mit stealth mode nötig
- Kann trotzdem blockiert werden
- Fallback: Manuelle Daten oder Cache

Nutzt:
- Playwright für Browser-Automation
- stealth mode für Cloudflare-Bypass
- Caching für wiederholte Anfragen
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json
import time


class TransfermarktScraper:
    """
    Scrapt Transfermarkt für:
    - Verletzte Spieler
    - Aufstellungen
    - Fitness-Status
    
    ⚠️ NICHT 100% ZUVERLÄSSIG wegen Cloudflare
    """
    
    BASE_URL = "https://www.transfermarkt.com"
    
    # Team URLs (vereinfacht - in Produktion dynamisch)
    TEAM_URLS = {
        'Bayern Munich': '/fc-bayern-muenchen/aufstellung',
        'Borussia Dortmund': '/borussia-dortmund/aufstellung',
        'RB Leipzig': '/rasenballsport-leipzig/aufstellung',
        'Bayer Leverkusen': '/bayer-04-leverkusen/aufstellung',
        'Eintracht Frankfurt': '/eintracht-frankfurt/aufstellung',
        'Arsenal': '/fc-arsenal/aufstellung',
        'Chelsea': '/fc-chelsea/aufstellung',
        'Liverpool': '/fc-liverpool/aufstellung',
        'Man City': '/manchester-city/aufstellung',
        'Man United': '/manchester-united/aufstellung',
        'Real Madrid': '/real-madrid/aufstellung',
        'Barcelona': '/fc-barcelona/aufstellung',
        'Juventus': '/juventus-turin/aufstellung',
        'PSG': '/fc-paris-saint-germain/aufstellung',
    }
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path("data/transfermarkt_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_duration = timedelta(hours=12)  # Cache 12h
        
    def _is_cache_valid(self, cache_file: Path) -> bool:
        """Prüft ob Cache noch gültig"""
        if not cache_file.exists():
            return False
        
        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        return datetime.now() - file_time < self.cache_duration
    
    def scrape_injuries(self, team: str) -> Dict:
        """
        Scrapt Verletzte für ein Team
        
        ⚠️ Kann fehlschlagen wegen Cloudflare!
        
        Returns:
            {
                'success': bool,
                'injuries': List[Dict],
                'error': str (optional),
                'from_cache': bool
            }
        """
        cache_file = self.cache_dir / f"{team.replace(' ', '_')}_injuries.json"
        
        # Versuche Cache
        if self._is_cache_valid(cache_file):
            with open(cache_file) as f:
                cached = json.load(f)
                cached['from_cache'] = True
                print(f"[Transfermarkt] {team}: Cache hit")
                return cached
        
        # Kein Cache oder veraltet → Scrape
        url_path = self.TEAM_URLS.get(team, '').replace('/aufstellung', '/verletzungen')
        
        if not url_path:
            return {
                'success': False,
                'injuries': [],
                'error': f'Team {team} nicht in URL-Datenbank',
                'from_cache': False
            }
        
        url = f"{self.BASE_URL}{url_path}"
        
        try:
            return self._scrape_with_playwright(team, url, cache_file)
            
        except Exception as e:
            print(f"[Transfermarkt] FEHLER: {e}")
            
            # Fallback: Alten Cache nehmen (auch wenn veraltet)
            if cache_file.exists():
                with open(cache_file) as f:
                    cached = json.load(f)
                    cached['from_cache'] = True
                    cached['error'] = f"Live scrape failed: {e}. Using old cache."
                    return cached
            
            # Kompletter Fail
            return {
                'success': False,
                'injuries': [],
                'error': f"Scraping failed: {e}",
                'from_cache': False
            }
    
    def _scrape_with_playwright(self, team: str, url: str, cache_file: Path) -> Dict:
        """
        Echter Scraping-Versuch mit Playwright
        
        ⚠️ Sehr instabil wegen Cloudflare!
        """
        print(f"[Transfermarkt] Scrape {team}...")
        
        with sync_playwright() as p:
            # Browser starten
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            
            try:
                # Navigieren
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Warte auf Content (Transfermarkt ist langsam)
                page.wait_for_selector('table.items', timeout=10000)
                
                # Extrahiere Verletzte
                injuries = []
                
                # Suche nach Verletzungs-Tabelle
                rows = page.query_selector_all('table.items tbody tr')
                
                for row in rows[:10]:  # Max 10
                    try:
                        cols = row.query_selector_all('td')
                        if len(cols) >= 4:
                            name = cols[0].inner_text().strip()
                            status = cols[2].inner_text().strip() if len(cols) > 2 else ''
                            seit = cols[3].inner_text().strip() if len(cols) > 3 else ''
                            
                            injuries.append({
                                'player': name,
                                'status': status,
                                'out_since': seit,
                                'team': team
                            })
                    except:
                        continue
                
                result = {
                    'success': True,
                    'injuries': injuries,
                    'error': None,
                    'from_cache': False,
                    'scraped_at': datetime.now().isoformat()
                }
                
                # Cache speichern
                with open(cache_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                browser.close()
                return result
                
            except PlaywrightTimeout:
                browser.close()
                raise Exception("Timeout - möglicherweise Cloudflare-Blockade")
                
            except Exception as e:
                browser.close()
                raise e
    
    def get_simple_injury_report(self, team: str) -> str:
        """Einfacher Report für Display"""
        result = self.scrape_injuries(team)
        
        if not result['success']:
            return f"⚠️ {team}: {result.get('error', 'Unbekannter Fehler')}"
        
        injuries = result['injuries']
        
        if len(injuries) == 0:
            return f"✅ {team}: Keine Verletzungen gemeldet"
        
        lines = [f"🚑 {team} Verletzungen ({len(injuries)}):"]
        for i in injuries[:5]:
            lines.append(f"  • {i['player']} - {i['status']}")
        
        if result.get('from_cache'):
            lines.append("  📦 (aus Cache)")

        return "\n".join(lines)
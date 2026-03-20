"""
Playwright-basierter Scraper für JavaScript-lastige Seiten
Alternative zu SBR API wenn Blockierung auftritt
"""
import asyncio
from typing import List, Optional
from datetime import datetime
import json
import re

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from scraper.sbr_scraper import OddsData, SBRScraper

# Typ-Hinweis nur wenn Playwright verfügbar
if PLAYWRIGHT_AVAILABLE:
    from playwright.async_api import Page
else:
    Page = None


class PlaywrightScraper:
    """
    Headless Chrome Scraper als Fallback
    Funktioniert auch auf Servern ohne GUI (headless=True)
    """
    
    def __init__(self, headless: bool = True, slow_mo: int = 100):
        self.headless = headless
        self.slow_mo = slow_mo
        
    async def fetch_sbr_odds(self, league_url: str) -> List[OddsData]:
        """
        Scraped SBR über Playwright (headless Chrome)
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("[Error] Playwright nicht installiert: pip install playwright && playwright install")
            return []
        
        print(f"[Playwright] Starte headless Chrome...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            page = await context.new_page()
            
            try:
                # Anti-Detection
                await page.evaluate("""() => {
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                }""")
                
                await page.goto(league_url, wait_until='networkidle', timeout=30000)
                
                # Warte auf Odds-Tabelle
                await page.wait_for_selector('[data-cy="odds-table"]', timeout=10000)
                
                # Extrahiere Daten
                matches = await self._extract_matches_from_page(page)
                
                await browser.close()
                return matches
                
            except Exception as e:
                print(f"[Playwright] Fehler: {e}")
                await browser.close()
                return []
    
    async def _extract_matches_from_page(self, page: Page) -> List[OddsData]:
        """Extrahiert Match-Daten aus geladener Seite"""
        # JavaScript-Extraktion
        matches_data = await page.evaluate("""() => {
            const rows = document.querySelectorAll('[data-cy="odds-row"]');
            const data = [];
            
            rows.forEach(row => {
                const teams = row.querySelector('.event-cell__name');
                const odds = row.querySelectorAll('.bookmaker-odds');
                
                if (teams && odds.length >= 3) {
                    data.push({
                        teams: teams.innerText.split(' vs '),
                        odds1: odds[0]?.innerText || '0',
                        oddsX: odds[1]?.innerText || '0', 
                        odds2: odds[2]?.innerText || '0'
                    });
                }
            });
            
            return data;
        }""")
        
        # Konvertiere zu OddsData
        odds_list = []
        for match in matches_data:
            try:
                odds_list.append(OddsData(
                    event_id=f"pw_{hash(match['teams'][0])}",
                    match_name=f"{match['teams'][0]} vs {match['teams'][1]}",
                    home_team=match['teams'][0],
                    away_team=match['teams'][1],
                    league="Unknown",
                    match_datetime=datetime.now(),
                    odds_1={"sbr": float(match['odds1'])},
                    odds_x={"sbr": float(match['oddsX'])},
                    odds_2={"sbr": float(match['odds2'])},
                    implied_prob_1=1/float(match['odds1']) if float(match['odds1']) > 0 else 0,
                    implied_prob_x=1/float(match['oddsX']) if float(match['oddsX']) > 0 else 0,
                    implied_prob_2=1/float(match['odds2']) if float(match['odds2']) > 0 else 0,
                    overround=0.0,
                    timestamp=datetime.now()
                ))
            except:
                continue
        
        return odds_list


class HybridScraper:
    """
    Kombiniert API-First mit Playwright-Fallback
    """
    
    def __init__(self):
        self.api_scraper = SBRScraper()
        self.pw_scraper = PlaywrightScraper(headless=True)
    
    async def get_odds(self, league: str = "bundesliga") -> List[OddsData]:
        """
        Versucht zuerst API, dann Playwright
        """
        # Versuche API
        matches = self.api_scraper.get_upcoming_matches(league)
        
        if matches:
            print(f"[Hybrid] API erfolgreich: {len(matches)} matches")
            return matches
        
        # Fallback zu Playwright
        print("[Hybrid] API fehlgeschlagen, versuche Playwright...")
        
        league_urls = {
            "bundesliga": "https://www.sportsbookreview.com/betting-odds/german-bundesliga/",
            "premier-league": "https://www.sportsbookreview.com/betting-odds/english-premier-league/",
        }
        
        url = league_urls.get(league, league_urls["bundesliga"])
        return await self.pw_scraper.fetch_sbr_odds(url)


# Sync-Wrapper für einfache Nutzung
def get_hybrid_odds(league: str = "bundesliga") -> List[OddsData]:
    """Synchrone Version des Hybrid Scrapers"""
    scraper = HybridScraper()
    try:
        return asyncio.run(scraper.get_odds(league))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(scraper.get_odds(league))
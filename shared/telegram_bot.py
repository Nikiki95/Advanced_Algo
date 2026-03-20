#!/usr/bin/env python3
"""
Shared Telegram Bot v2 for Betting Algorithm
- CLV tracking alerts
- Correlated bet alerts
- Market-specific formatting (1X2, DC, O/U, Spread, Totals)
- Performance reports with CLV
"""

import os
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BettingAlertBot:
    """Telegram Bot for all betting alerts."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.enabled = bool(self.bot_token and self.chat_id)
        if not self.enabled:
            logger.warning("Telegram not configured")

    async def send_message(self, text: str, parse_mode: Optional[str] = "Markdown") -> bool:
        if not self.enabled:
            return False
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id, "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        return True
                    logger.error(f"Telegram error: {await resp.text()}")
                    return False
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False

    def send_sync(self, text: str, parse_mode: Optional[str] = "Markdown") -> bool:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.send_message(text, parse_mode=parse_mode)).result()
            else:
                return loop.run_until_complete(self.send_message(text, parse_mode=parse_mode))
        except RuntimeError:
            return asyncio.run(self.send_message(text, parse_mode=parse_mode))
        except Exception as e:
            logger.error(f"Sync send error: {e}")
            return False

    def send_plain(self, text: str) -> bool:
        return self.send_sync(text, parse_mode=None)

    # ── UNIVERSAL VALUE BET ALERT ────────────────

    def send_value_bet(self, sport: str, bet: Dict) -> bool:
        """Universal value bet alert for any sport/market."""
        icons = {'football': '⚽', 'nba': '🏀', 'nfl': '🏈'}
        conf_emoji = {'high': '🔥', 'medium': '⭐', 'low': '👀'}
        icon = icons.get(sport, '🎯')
        ce = conf_emoji.get(bet.get('confidence', 'medium'), '⭐')

        market = bet.get('market', bet.get('bet_type', ''))
        text = f"""{ce} *{sport.upper()} VALUE BET*

{icon} {bet.get('home_team', '')} vs {bet.get('away_team', '')}
📊 {market.upper()}: *{bet.get('selection', '')}*
💰 Quote: `{bet.get('odds', 0):.2f}` @{bet.get('bookmaker', '')}
🧠 Modell: `{bet.get('model_prob', 0)*100:.1f}%`
📈 Value: `+{bet.get('value', 0)*100:.1f}%`
💵 Einsatz: `{bet.get('kelly_stake', 0):.2f}€`
🏷 Konfidenz: `{bet.get('confidence', '').upper()}`

_{datetime.now():%H:%M}_"""

        return self.send_sync(text)

    # ── CORRELATED BET ALERT (NEW) ───────────────

    def send_correlation_alert(self, sport: str, correlation: Dict) -> bool:
        """Alert for detected correlated value bets."""
        text = f"""🔗 *{sport.upper()} KORRELIERTE BETS*

📊 {correlation.get('description', '')}
💪 Stärke: `{correlation.get('strength', '').upper()}`
📈 Combined Value: `{correlation.get('combined_value', 0)*100:.1f}%`

_Tipp: Diese Bets verstärken sich gegenseitig._
_{datetime.now():%H:%M}_"""

        return self.send_sync(text)

    # ── PERFORMANCE REPORT (with CLV) ────────────

    def send_performance_report(self, perf: Dict) -> bool:
        """Daily/weekly performance report with CLV analysis."""
        sport = perf.get('sport', 'ALL').upper()
        days = perf.get('period_days', 30)

        text = f"""📊 *{sport} PERFORMANCE ({days}d)*

📈 Bets: `{perf.get('total_bets', 0)}` | W: `{perf.get('wins', 0)}` | L: `{perf.get('losses', 0)}`
🎯 Win-Rate: `{perf.get('win_rate', 0)}%`
💰 ROI: `{perf.get('roi_percent', 0):+.1f}%`
💵 Profit: `{perf.get('total_profit', 0):+.2f}€`"""

        # CLV
        clv = perf.get('clv', {})
        if clv.get('available'):
            text += f"""

📈 *CLV Analyse:*
   Avg CLV: `{clv.get('avg_clv_percent', 0):+.2f}%`
   Positive Rate: `{clv.get('positive_clv_rate', 0)}%`
   Status: `{clv.get('interpretation', 'N/A')}`"""

        # Market breakdown
        mp = perf.get('market_performance', {})
        if mp:
            text += "\n\n📊 *By Market:*"
            for market, stats in mp.items():
                text += f"\n   {market}: {stats['bets']}x, WR {stats['win_rate']}%"

        text += f"\n\n_{datetime.now():%d.%m.%Y %H:%M}_"
        return self.send_sync(text)

    # ── SUMMARY ALERTS ───────────────────────────

    def send_daily_summary(self, sport: str, bets_found: int,
                           leagues: List[str] = None,
                           correlations: int = 0) -> bool:
        icons = {'football': '⚽', 'nba': '🏀', 'nfl': '🏈'}
        icon = icons.get(sport, '🎯')
        text = f"""📊 *{sport.upper()} ÜBERSICHT*

{icon} {bets_found} Value-Bets gefunden"""

        if leagues:
            text += f"\n🏆 Ligen: {', '.join(leagues)}"
        if correlations > 0:
            text += f"\n🔗 {correlations} korrelierte Muster"

        text += f"\n🕐 {datetime.now():%d.%m.%Y %H:%M}"
        return self.send_sync(text)

    # ── SYSTEM ───────────────────────────────────

    def send_error(self, message: str, sport: str = "system") -> bool:
        text = f"⚠️ *{sport.upper()} FEHLER*\n\n```{message[:400]}```"
        return self.send_sync(text)

    def send_startup(self, sport: str) -> bool:
        icons = {'football': '⚽', 'nba': '🏀', 'nfl': '🏈'}
        return self.send_sync(f"{icons.get(sport, '🤖')} *{sport.upper()} Analyzer gestartet*")


alert_bot = BettingAlertBot()

if __name__ == "__main__":
    bot = BettingAlertBot()
    if bot.enabled:
        bot.send_sync("🤖 *Test Alert v2*\n\nBot mit CLV-Tracking bereit!")
        print("Test sent")
    else:
        print("Not configured")

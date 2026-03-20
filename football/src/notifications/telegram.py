"""
Telegram Notifications für Value-Bet Alerts
"""
import asyncio
from typing import List, Optional
from datetime import datetime
import os

from config import config

# Optional: python-telegram-bot
try:
    from telegram import Bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class TelegramNotifier:
    """
    Sendet Value-Bet Alerts via Telegram Bot
    """
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.bot = None
        
        if TELEGRAM_AVAILABLE and self.token:
            self.bot = Bot(token=self.token)
    
    def is_configured(self) -> bool:
        """Prüft ob Telegram konfiguriert ist"""
        return bool(self.bot and self.chat_id)
    
    async def send_alert(self, value_bets: List, test_mode: bool = False) -> bool:
        """
        Sendet Value-Bet Benachrichtigung
        
        Args:
            value_bets: Liste der ValueBet Objekte
            test_mode: Nur Test-Nachricht
        """
        if not self.is_configured():
            print("[Telegram] Nicht konfiguriert - überspringe")
            return False
        
        if test_mode:
            return await self.send_test_message()
        
        if not value_bets:
            return False
        
        try:
            message = self._format_message(value_bets)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            print(f"[Telegram] Alert gesendet an {self.chat_id}")
            return True
            
        except Exception as e:
            print(f"[Telegram] Fehler beim Senden: {e}")
            return False
    
    async def send_test_message(self) -> bool:
        """Sendet Test-Nachricht"""
        if not self.is_configured():
            print("[Telegram] Token oder Chat ID fehlt")
            return False
        
        try:
            message = (
                "🤖 *Value-Bet Bot Test*\n\n"
                "Der Benachrichtigungs-Service funktioniert!\n"
                f"Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                "Du wirst benachrichtigt, wenn ein Value-Bet gefunden wird."
            )
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            print("[Telegram] Test-Nachricht gesendet!")
            return True
            
        except Exception as e:
            print(f"[Telegram] Test fehlgeschlagen: {e}")
            return False
    
    def _format_message(self, value_bets: List) -> str:
        """Formatiert Value-Bets für Telegram"""
        lines = [
            "🔥 *VALUE-BET ALERTS* 🔥",
            f"_{datetime.now().strftime('%d.%m.%Y %H:%M')}_",
            "",
        ]
        
        for bet in value_bets[:5]:  # Max 5 Bets
            # Emoji je nach Konfidenz
            if bet.confidence == 'high':
                emoji = '🟢'
            elif bet.confidence == 'medium':
                emoji = '🟡'
            else:
                emoji = '⚪'
            
            lines.append(f"{emoji} *{bet.home_team} vs {bet.away_team}*")
            lines.append(f"💰 Wette: {bet.selection} ({bet.bet_type})")
            lines.append(f"📊 Quote: `{bet.best_odds:.2f}` @{bet.bookmaker}")
            lines.append(f"🧠 Modell: {bet.model_probability:.0%}")
            lines.append(f"📈 Market: {bet.market_probability:.0%}")
            lines.append(f"⚡ Value: *{bet.value_percentage:.1%}* (ROI: {bet.roi:+.1f}%)")
            lines.append(f"🎯 Kelly: {bet.kelly_stake:.0f} coins")
            lines.append(f"🕐 {bet.match_datetime.strftime('%a %H:%M')}")
            lines.append("")
        
        lines.append(f"_Gefunden: {len(value_bets)} Value-Bets_")
        lines.append(f"_Zeit: {datetime.now().strftime('%H:%M')}_")
        
        return "\n".join(lines)
    
    # === NBA / NFL ALERTS ===
    
    async def send_nba_value_bet(self, bet_data: dict) -> bool:
        """Sendet NBA Value-Bet Alert."""
        if not self.is_configured():
            return False
        
        emoji = {"high": "🔥", "medium": "🏀", "low": "👀"}.get(bet_data.get('confidence'), "🏀")
        
        message = (
            f"{emoji} *NBA VALUE BET*\n\n"
            f"🏀 {bet_data.get('match', 'Unknown')}\n"
            f"📊 {bet_data.get('market', '').upper()}: {bet_data.get('selection', '')}\n\n"
            f"💰 Quote: `⌗{bet_data.get('odds', 0):.2f}`\n"
            f"🧠 Modell: {bet_data.get('model_prob', 0)*100:.1f}%\n"
            f"📈 Edge: *+{bet_data.get('value', 0)*100:.1f}%*\n"
            f"📐 Kelly: {bet_data.get('kelly', 0):.1%}\n"
            f"💵 Einsatz: ${bet_data.get('bet_size', 0):.2f}\n\n"
            f"_{datetime.now().strftime('%H:%M')}_"
        )
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id, 
                text=message, 
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return True
        except Exception as e:
            print(f"[Telegram] NBA Alert Fehler: {e}")
            return False
    
    async def send_nfl_value_bet(self, bet_data: dict) -> bool:
        """Sendet NFL Value-Bet Alert."""
        if not self.is_configured():
            return False
        
        emoji = {"high": "🔥", "medium": "🏈", "low": "👀"}.get(bet_data.get('confidence'), "🏈")
        
        message = (
            f"{emoji} *NFL VALUE BET*\n\n"
            f"🏈 {bet_data.get('match', 'Unknown')}\n"
            f"📊 {bet_data.get('market', '').upper()}: {bet_data.get('selection', '')}\n\n"
            f"💰 Quote: `⌗{bet_data.get('odds', 0):.2f}`\n"
            f"📈 Edge: *+{bet_data.get('value', 0)*100:.1f}%*\n"
            f"💵 Einsatz: ${bet_data.get('bet_size', 0):.2f}\n\n"
            f"_{datetime.now().strftime('%H:%M')}_"
        )
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id, 
                text=message, 
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return True
        except Exception as e:
            print(f"[Telegram] NFL Alert Fehler: {e}")
            return False
    
    def sync_send_nba_alert(self, bet_data: dict) -> bool:
        """Synchrone NBA Alert Wrapper."""
        try:
            return asyncio.run(self.send_nba_value_bet(bet_data))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_nba_value_bet(bet_data))
    
    def sync_send_nfl_alert(self, bet_data: dict) -> bool:
        """Synchrone NFL Alert Wrapper."""
        try:
            return asyncio.run(self.send_nfl_value_bet(bet_data))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_nfl_value_bet(bet_data))
    
    async def send_daily_summary(self, stats: dict) -> bool:
        """Sendet tägliche Zusammenfassung"""
        if not self.is_configured():
            return False
        
        message = (
            f"📊 *Tagesübersicht*\n\n"
            f"Getestet: {stats.get('matches_checked', 0)} Spiele\n"
            f"Value-Bets: {stats.get('value_bets_found', 0)}\n"
            f"Gestern gewonnen: {stats.get('yesterday_wins', 0)}/{stats.get('yesterday_total', 0)}\n"
            f"ROI: {stats.get('roi', 0):.1f}%\n"
        )
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            return True
        except Exception as e:
            print(f"[Telegram] Summary-Fehler: {e}")
            return False
    
    def sync_send_alert(self, value_bets: List) -> bool:
        """Synchrone Wrapper für einfache Nutzung"""
        try:
            return asyncio.run(self.send_alert(value_bets))
        except RuntimeError:
            # Event loop already running
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_alert(value_bets))
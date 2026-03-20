#!/usr/bin/env python3
"""
Setup-Helfer für Telegram Integration
Testet Verbindung und gibt Anleitung
"""
import os
import sys

sys.path.insert(0, "src")

from config import config
from notifications.telegram import TelegramNotifier


def check_telegram_config():
    """Prüft Telegram-Konfiguration"""
    print("📱 Telegram Setup Check")
    print("=" * 50)
    
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN nicht gesetzt")
        print("\n🔧 So holst du dir einen Token:")
        print("   1. Öffne Telegram")
        print("   2. Suche nach: @BotFather")
        print("   3. Schreibe: /newbot")
        print("   4. Folge den Anweisungen (Name + Username)")
        print("   5. Kopiere den Token (z.B. 123456789:ABCdefGH...)")
        print("   6. Füge ihn in .env ein")
        return False
    
    if not chat_id:
        print("❌ TELEGRAM_CHAT_ID nicht gesetzt")
        print("\n🔧 So findest du deine Chat-ID:")
        print("   1. Suche in Telegram nach: @userinfobot")
        print("   2. Schreibe: /start")
        print("   3. Kopiere die ID (z.B. 123456789)")
        print("   4. Füge sie in .env ein")
        return False
    
    print(f"✅ Token gesetzt: {token[:20]}...")
    print(f"✅ Chat ID gesetzt: {chat_id}")
    print()
    
    # Teste Verbindung
    print("🔄 Teste Verbindung...")
    notifier = TelegramNotifier()
    
    if notifier.is_configured():
        print("✅ Bot ist konfiguriert!")
        print()
        
        # Sende Test-Nachricht
        test = input("📤 Soll ich eine Test-Nachricht senden? (j/n): ").lower()
        if test == 'j':
            success = notifier.sync_send_alert([], test_mode=True)
            if success:
                print("✅ Test-Nachricht gesendet!")
                print("   Check dein Telegram!")
            else:
                print("❌ Senden fehlgeschlagen")
                print("   Prüfe ob Token und Chat-ID korrekt sind")
        
        return True
    else:
        print("❌ Bot konnte nicht initialisiert werden")
        print("   Prüfe ob python-telegram-bot installiert ist:")
        print("   ./venv/bin/pip install python-telegram-bot")
        return False


def setup_cron():
    """Zeigt Cron-Setup Anleitung"""
    print("\n🕐 Cron-Job Setup")
    print("=" * 50)
    
    print("\nOption 1: Host-Cron (empfohlen)")
    print("-" * 50)
    print("Bearbeite Crontab:")
    print("  crontab -e")
    print()
    print("Füge hinzu (alle 30 Minuten werktags):")
    print('  */30 8-22 * * 1-5 cd ~/betting-algorithm && ./venv/bin/python cron_runner.py >> logs/cron.log 2>&1')
    print()
    
    print("Option 2: Docker-Cron")
    print("-" * 50)
    print("Starte:")
    print("  ./run.sh cron-start")
    print()
    print("Logs:")
    print("  ./run.sh logs")
    

if __name__ == "__main__":
    print("🚀 Value-Bet Algorithm Setup")
    print("=" * 50)
    print()
    
    # Telegram Check
    telegram_ok = check_telegram_config()
    
    # Cron Setup
    setup_cron()
    
    # Zusammenfassung
    print("\n" + "=" * 50)
    print("📋 Zusammenfassung")
    print("=" * 50)
    
    if telegram_ok:
        print("✅ Telegram: Bereit für Alerts")
    else:
        print("⚠️  Telegram: Nicht konfiguriert (optional)")
    
    print()
    print("🎯 Nächste Schritte:")
    print("   1. ./venv/bin/python historical_value.py")
    print("      → Manuelle Value-Analyse")
    print()
    print("   2. ./venv/bin/python cron_runner.py")
    print("      → Einzelner automatischer Check")
    print()
    print("   3. Crontab einrichten (siehe oben)")
    print("      → Regelmäßige automatische Checks")
#!/usr/bin/env python3
"""
CLI Tool for tracking bet results
Usage: python track_result.py [bet_id] [won|lost] [odds] (optional: actual odds if different)
"""

import sys
import sqlite3
from datetime import datetime

def track_result(bet_id, result, actual_odds=None):
    conn = sqlite3.connect('data/value_tracking.db')
    c = conn.cursor()
    
    # Get bet info
    c.execute('SELECT odds, stake FROM bets WHERE id = ?', (bet_id,))
    row = c.fetchone()
    
    if not row:
        print(f"❌ Bet #{bet_id} not found")
        conn.close()
        return
    
    odds, stake = row
    if actual_odds:
        odds = float(actual_odds)
    
    # Calculate P/L
    if result.lower() == 'won':
        pl = (odds - 1) * stake if stake > 0 else 0
    elif result.lower() == 'lost':
        pl = -stake if stake > 0 else 0
    else:
        print(f"❌ Invalid result: {result} (use 'won' or 'lost')")
        conn.close()
        return
    
    # Update bet
    c.execute('''
        UPDATE bets 
        SET result = ?, profit_loss = ?, settled_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (result.lower(), pl, bet_id))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Bet #{bet_id} marked as {result.upper()}")
    if stake > 0:
        print(f"   P/L: €{pl:.2f}")

def list_pending():
    conn = sqlite3.connect('data/value_tracking.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, date, sport, match, pick, bet_type, odds, value_pct
        FROM bets WHERE result = 'pending'
        ORDER BY date DESC
    ''')
    
    rows = c.fetchall()
    
    if not rows:
        print("➖ No pending bets")
        conn.close()
        return
    
    print(f"\n📝 PENDING BETS ({len(rows)} total):")
    print("-"*80)
    for row in rows:
        bid, date, sport, match, pick, btype, odds, val = row
        print(f"\nID {bid}: {sport} - {match}")
        print(f"      {pick} ({btype}) @ {odds:.2f} ({val:+.1%} value)")
        print(f"      Date: {date}")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python track_result.py list           # List pending bets")
        print("  python track_result.py [id] [won|lost] [actual_odds]")
        print("\nExamples:")
        print("  python track_result.py 1 won")
        print("  python track_result.py 2 lost")
        sys.exit(1)
    
    if sys.argv[1] == 'list':
        list_pending()
    elif len(sys.argv) >= 3:
        bet_id = sys.argv[1]
        result = sys.argv[2]
        actual_odds = sys.argv[3] if len(sys.argv) > 3 else None
        track_result(bet_id, result, actual_odds)
    else:
        print("❌ Invalid arguments")

#!/usr/bin/env python3
"""
Daily Value Bet Report Generator
Run this after daily value bet identification
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

def generate_daily_report():
    conn = sqlite3.connect('data/value_tracking.db')
    c = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    print("\n" + "="*80)
    print(f"📊 DAILY VALUE BET REPORT - {today}")
    print("="*80)
    
    # Today's bets
    c.execute('''
        SELECT sport, league, match, pick, bet_type, odds, model_prob, value_pct
        FROM bets WHERE date = ? ORDER BY value_pct DESC
    ''', (today,))
    
    todays = c.fetchall()
    
    if todays:
        print(f"\n🎯 TODAY'S VALUE BETS ({len(todays)} total):")
        print("-"*80)
        for i, (sport, league, match, pick, btype, odds, prob, val) in enumerate(todays, 1):
            print(f"\n{i}. {sport} - {league}")
            print(f"   Match: {match}")
            print(f"   Pick: {pick} ({btype})")
            print(f"   Odds: {odds:.2f} | Model: {prob:.1%} | Value: {val:+.1%}")
            ev = odds * prob - 1
            print(f"   Expected Value: {ev:+.1%}")
    else:
        print("\n➖ No value bets identified for today")
    
    # Overall stats
    c.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(profit_loss) as pl
        FROM bets
    ''')
    
    total, won, lost, pl = c.fetchone()
    
    if total and total > 0:
        print(f"\n📈 ALL-TIME PERFORMANCE:")
        print(f"   Total Bets: {total}")
        print(f"   Won: {won or 0} | Lost: {lost or 0}")
        print(f"   Profit/Loss: €{pl or 0:.2f}")
        if (won or 0) + (lost or 0) > 0:
            wr = (won or 0) / ((won or 0) + (lost or 0)) * 100
            print(f"   Win Rate: {wr:.1f}%")
    
    conn.close()
    
    print("\n" + "="*80)
    print("💡 TIP: Use /track_result [bet_id] [won|lost] to update results")
    print("="*80)

if __name__ == "__main__":
    generate_daily_report()

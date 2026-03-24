#!/usr/bin/env python3
"""
Value Bet Tracking & Analytics System
Tracks performance of value bets with success metrics
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import sys
sys.path.insert(0, '.')

DB_PATH = Path('data/value_tracking.db')

def init_database():
    """Initialize tracking database"""
    DB_PATH.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Main bets table
    c.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            sport TEXT NOT NULL,
            league TEXT,
            match TEXT NOT NULL,
            pick TEXT NOT NULL,
            bet_type TEXT NOT NULL,
            odds REAL NOT NULL,
            model_prob REAL NOT NULL,
            value_pct REAL NOT NULL,
            stake REAL DEFAULT 0,
            result TEXT DEFAULT 'pending',
            profit_loss REAL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP
        )
    ''')
    
    # Performance metrics table (daily summary)
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_metrics (
            date TEXT PRIMARY KEY,
            sport TEXT,
            total_bets INTEGER DEFAULT 0,
            won INTEGER DEFAULT 0,
            lost INTEGER DEFAULT 0,
            pending INTEGER DEFAULT 0,
            total_staked REAL DEFAULT 0,
            total_return REAL DEFAULT 0,
            roi_pct REAL DEFAULT 0,
            avg_value_pct REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Tracking database initialized")

def add_bet(date, sport, league, match, pick, bet_type, odds, model_prob, value_pct, stake=0, notes=""):
    """Add a new bet to track"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO bets (date, sport, league, match, pick, bet_type, odds, model_prob, value_pct, stake, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date, sport, league, match, pick, bet_type, odds, model_prob, value_pct, stake, notes))
    
    bet_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return bet_id

def settle_bet(bet_id, result, profit_loss):
    """Settle a bet with result"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        UPDATE bets 
        SET result = ?, profit_loss = ?, settled_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (result, profit_loss, bet_id))
    
    conn.commit()
    conn.close()

def get_performance_summary(days=30):
    """Get performance summary for last N days"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # Overall stats
    c.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(profit_loss) as total_pl,
            SUM(stake) as total_staked,
            AVG(value_pct) as avg_value
        FROM bets
        WHERE date >= ?
    ''', (cutoff,))
    
    row = c.fetchone()
    conn.close()
    
    if row and row[0] > 0:
        total, won, lost, pending, pl, staked, avg_val = row
        roi = (pl / staked * 100) if staked else 0
        win_rate = (won / (won + lost) * 100) if (won + lost) > 0 else 0
        
        return {
            'total_bets': total,
            'won': won or 0,
            'lost': lost or 0,
            'pending': pending or 0,
            'win_rate': win_rate,
            'total_profit': pl or 0,
            'total_staked': staked or 0,
            'roi_pct': roi,
            'avg_value_pct': (avg_val or 0) * 100
        }
    
    return None

def get_todays_bets():
    """Get today's bets"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    c.execute('''
        SELECT * FROM bets WHERE date = ? ORDER BY value_pct DESC
    ''', (today,))
    
    rows = c.fetchall()
    conn.close()
    
    return rows

def generate_report(days=7):
    """Generate performance report"""
    print("\n" + "="*80)
    print(f"📊 VALUE BET ANALYTICS REPORT (Last {days} days)")
    print("="*80)
    
    summary = get_performance_summary(days)
    
    if not summary or summary['total_bets'] == 0:
        print("\n➖ No bets tracked yet")
        return
    
    print(f"\n📈 OVERALL PERFORMANCE:")
    print(f"   Total Bets: {summary['total_bets']}")
    print(f"   Won: {summary['won']} | Lost: {summary['lost']} | Pending: {summary['pending']}")
    print(f"   Win Rate: {summary['win_rate']:.1f}%")
    print(f"   Total Staked: €{summary['total_staked']:.2f}")
    print(f"   Profit/Loss: €{summary['total_profit']:.2f}")
    print(f"   ROI: {summary['roi_pct']:.2f}%")
    print(f"   Avg Value %: {summary['avg_value_pct']:.1f}%")
    
    # Sport breakdown
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    c.execute('''
        SELECT sport, COUNT(*), SUM(profit_loss), AVG(value_pct)
        FROM bets
        WHERE date >= ?
        GROUP BY sport
    ''', (cutoff,))
    
    print(f"\n🏆 BY SPORT:")
    for row in c.fetchall():
        sport, count, pl, avg_val = row
        print(f"   {sport}: {count} bets, €{pl:.2f} P/L, {avg_val*100:.1f}% avg value")
    
    conn.close()

if __name__ == "__main__":
    init_database()
    generate_report()

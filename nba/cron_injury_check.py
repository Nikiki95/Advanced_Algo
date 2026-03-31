#!/usr/bin/env python3
"""
NBA Injury Check - Daily at 20:00
Fetches injury data from API-Sports or other sources
"""

import sqlite3
import requests
from datetime import datetime
from pathlib import Path

DB_PATH = Path('data/research.db')

def init_db():
    """Initialize injury table"""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS injuries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport TEXT NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            injury TEXT,
            status TEXT,  -- 'Out', 'Doubtful', 'Questionable', 'Active'
            date_reported TEXT,
            date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sport, player_name, team)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Injury database initialized")

def fetch_nba_injuries():
    """Fetch NBA injuries from API-Sports"""
    
    # Try to get API key
    api_key = None
    try:
        with open('secrets/.env') as f:
            for line in f:
                if line.startswith('APISPORTS_KEY='):
                    api_key = line.strip().split('=', 1)[1]
                    break
    except:
        pass
    
    if not api_key:
        print("⚠️  No API-Sports key found")
        print("   Set APISPORTS_KEY in secrets/.env for injury data")
        return []
    
    try:
        url = "https://v1.basketball.api-sports.io/injuries"
        headers = {
            'x-apisports-key': api_key
        }
        params = {
            'league': '12',  # NBA
            'season': '2025-2026'
        }
        
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            return data.get('response', [])
        else:
            print(f"⚠️  API error: {resp.status_code}")
            return []
            
    except Exception as e:
        print(f"⚠️  Fetch error: {e}")
        return []

def update_injuries():
    """Update injury database"""
    
    init_db()
    
    print("🔍 Fetching NBA injuries...")
    injuries = fetch_nba_injuries()
    
    if not injuries:
        print("⚠️  No injury data available")
        print("   Without APISPORTS_KEY, injury tracking is disabled")
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    added = 0
    for injury in injuries:
        player = injury.get('player', {}).get('name', 'Unknown')
        team = injury.get('team', {}).get('name', 'Unknown')
        injury_type = injury.get('type', 'Unknown')
        status = 'Out'  # API-Sports doesn't provide status, default to Out
        
        try:
            c.execute('''
                INSERT OR REPLACE INTO injuries 
                (sport, player_name, team, injury, status, date_reported)
                VALUES (?, ?, ?, ?, ?, date('now'))
            ''', ('NBA', player, team, injury_type, status))
            added += 1
        except Exception as e:
            print(f"⚠️  Error adding {player}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Added/updated {added} injuries")

def get_impactful_injuries():
    """Get injuries that would impact betting"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        SELECT player_name, team, status, injury
        FROM injuries
        WHERE sport = 'NBA' AND status IN ('Out', 'Doubtful')
        ORDER BY team, player_name
    ''')
    
    injuries = c.fetchall()
    conn.close()
    
    return injuries

if __name__ == "__main__":
    print("="*60)
    print("🏥 NBA INJURY CHECK")
    print("="*60)
    
    update_injuries()
    
    # Show current impactful injuries
    impactful = get_impactful_injuries()
    if impactful:
        print("\n📋 Current Significant Injuries:")
        print("-"*60)
        for player, team, status, injury in impactful[:10]:
            print(f"   {player} ({team}): {status} - {injury}")
    
    print("\n" + "="*60)
    print("✅ Done!")

#!/usr/bin/env python3
"""
NBA Results Checker via Brave Search
Automatically checks game results and updates betting tracking
"""

import sqlite3
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import re
import sys
sys.path.insert(0, '.')

DB_PATH = Path('data/value_tracking.db')
BRAVE_API_KEY = None  # Will be loaded from env if available

def search_nba_results(date_str):
    """Search for NBA results using Brave Search"""
    
    # Format date for search query
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    date_formatted = date_obj.strftime('%B %d, %Y')
    
    query = f"NBA results {date_formatted} scores"
    
    try:
        # Try to get API key from env
        with open('secrets/.env') as f:
            for line in f:
                if line.startswith('BRAVE_API_KEY='):
                    BRAVE_API_KEY = line.strip().split('=', 1)[1]
                    break
        
        if not BRAVE_API_KEY:
            print("⚠️  No Brave API key found, using web fallback...")
            return None
        
        # Brave Search API
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            'Accept': 'application/json',
            'X-Subscription-Token': BRAVE_API_KEY
        }
        params = {
            'q': query,
            'count': 10
        }
        
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('web', {}).get('results', [])
            
            # Extract scores from results
            scores = []
            for result in results:
                desc = result.get('description', '')
                # Look for score patterns like "Team A 120, Team B 110" or "Team A 120-110 Team B"
                score_patterns = [
                    r'(\w+[\s\w]*)\s+(\d+)\s*[-,]\s*(\d+)\s+(\w+[\s\w]*)',
                    r'(\d+)\s*[-,]\s*(\d+)\s+(\w+)\s+vs\s+(\w+)'
                ]
                
                for pattern in score_patterns:
                    matches = re.findall(pattern, desc)
                    for match in matches:
                        scores.append(match)
            
            return scores
        else:
            print(f"⚠️  Brave API error: {resp.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️  Search error: {e}")
        return None

def get_pending_bets(date_str):
    """Get all pending bets for a specific date"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        SELECT id, match, pick, bet_type, odds
        FROM bets
        WHERE date = ? AND sport = 'NBA' AND result = 'pending'
    """, (date_str,))
    
    bets = c.fetchall()
    conn.close()
    
    return bets

def check_result_against_spread(match_teams, pick, bet_type):
    """
    Check if bet won Straight Up (SU) and Against The Spread (ATS)
    Returns: (su_result, ats_result, home_score, away_score)
    """
    # This would need actual game data
    # For now, placeholder - in production would parse from web search
    return None, None, None, None

def update_bet_result(bet_id, result, pl):
    """Update bet result in database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        UPDATE bets
        SET result = ?, profit_loss = ?, settled_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (result, pl, bet_id))
    
    conn.commit()
    conn.close()

def track_performance():
    """Track overall performance metrics"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # SU (Straight Up) Stats
    c.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(profit_loss) as pl,
            AVG(odds) as avg_odds,
            AVG(value_pct) as avg_value
        FROM bets
        WHERE sport = 'NBA' AND result != 'pending'
    """)
    
    su_stats = c.fetchone()
    
    print("\n📊 STRAIGHT UP (SU) PERFORMANCE:")
    print("-"*60)
    if su_stats and su_stats[0] > 0:
        total, won, lost, pl, avg_odds, avg_val = su_stats
        win_rate = (won/total*100) if total > 0 else 0
        print(f"   Total Bets:  {total}")
        print(f"   Won:         {won} ({win_rate:.1f}%)")
        print(f"   Lost:        {lost}")
        print(f"   Profit/Loss: €{pl:.2f}")
        print(f"   Ø Odds:      {avg_odds:.2f}")
        print(f"   Ø Value:     {avg_val*100:.1f}%")
    else:
        print("   No settled bets yet")
    
    # By Date
    print("\n📅 PERFORMANCE BY DATE:")
    print("-"*60)
    
    c.execute("""
        SELECT 
            date,
            COUNT(*) as total,
            SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as won,
            SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(profit_loss) as pl
        FROM bets
        WHERE sport = 'NBA' AND result != 'pending'
        GROUP BY date
        ORDER BY date DESC
    """)
    
    for row in c.fetchall():
        date, total, won, lost, pl = row
        wr = (won/total*100) if total > 0 else 0
        pl_str = f"€{pl:.2f}" if pl else "€0.00"
        print(f"   {date}: {won}/{total} ({wr:.0f}%) | P/L: {pl_str}")
    
    conn.close()

def main():
    print("🏀 NBA RESULTS CHECKER")
    print("="*60)
    
    # Check yesterday's results
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n🔍 Checking results for {yesterday}...")
    
    pending = get_pending_bets(yesterday)
    
    if not pending:
        print("   No pending bets to check")
    else:
        print(f"   Found {len(pending)} pending bets")
        
        # Search for results
        results = search_nba_results(yesterday)
        
        if results:
            print(f"   Found {len(results)} potential score matches")
            # Process results...
            for bet_id, match, pick, btype, odds in pending:
                print(f"\n   Checking: {match} - {pick}")
                # Would parse actual results here
        else:
            print("   Could not retrieve results automatically")
            print("   Manual update required")
    
    # Show current performance
    track_performance()
    
    print("\n" + "="*60)
    print("✅ Done!")

if __name__ == "__main__":
    main()

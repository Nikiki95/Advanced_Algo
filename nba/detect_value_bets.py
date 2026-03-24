#!/usr/bin/env python3
"""
NBA Value Bet Detection with Berlin Timezone
Detects value bets based on Berlin local time (UTC+1)
"""

import os
import pickle
import requests
import sqlite3
from datetime import datetime, timedelta
import math

# BERLIN TIMEZONE (UTC+1)
BERLIN_OFFSET = timedelta(hours=1)

def get_berlin_date(offset_days=0):
    """Get date in Berlin timezone"""
    berlin_now = datetime.now() + BERLIN_OFFSET + timedelta(days=offset_days)
    return berlin_now.strftime('%Y-%m-%d')

def detect_nba_value_bets(target_date=None):
    """Detect NBA value bets for target date (Berlin time)"""
    if target_date is None:
        target_date = get_berlin_date()
    
    # Load API key
    with open('secrets/.env') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value
    
    KEY = os.environ.get('THEODDS_API_KEY')
    
    # Load Model
    with open('nba/models/elo_model_202603.pkl', 'rb') as f:
        elos = pickle.load(f)['elos']
    
    TEAM_MAP = {
        "Brooklyn Nets": "Brooklyn", "New York Knicks": "New York",
        "Detroit Pistons": "Detroit", "Golden State Warriors": "Golden State",
        "Houston Rockets": "Houston", "Atlanta Hawks": "Atlanta",
        "Memphis Grizzlies": "Memphis", "Boston Celtics": "Boston",
        "Minnesota Timberwolves": "Minnesota", "Portland Trail Blazers": "Portland",
        "Washington Wizards": "Washington", "Oklahoma City Thunder": "Oklahoma City",
        "New Orleans Pelicans": "New Orleans", "Cleveland Cavaliers": "Cleveland",
        "Orlando Magic": "Orlando", "LAL": "LAL", "Los Angeles Lakers": "LAL",
        "San Antonio Spurs": "San Antonio", "Indiana Pacers": "Indiana",
        "Dallas Mavericks": "Dallas", "Los Angeles Clippers": "LA Clippers",
        "Utah Jazz": "Utah", "Philadelphia 76ers": "Philadelphia",
        "Phoenix Suns": "Phoenix", "Milwaukee Bucks": "Milwaukee",
        "Toronto Raptors": "Toronto", "Denver Nuggets": "Denver",
        "Miami Heat": "Miami", "Chicago Bulls": "Chicago",
        "Charlotte Hornets": "Charlotte", "Sacramento Kings": "Sacramento",
    }
    
    # Fetch games
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
    resp = requests.get(url, params={'apiKey': KEY, 'regions': 'eu', 'markets': 'h2h'}, timeout=30)
    matches = resp.json()
    
    value_bets = []
    
    for m in matches:
        if isinstance(m, dict):
            # Convert UTC to Berlin time
            utc_time = m['commence_time']
            utc_dt = datetime.fromisoformat(utc_time.replace('Z', '+00:00'))
            berlin_dt = utc_dt + BERLIN_OFFSET
            berlin_date = berlin_dt.strftime('%Y-%m-%d')
            
            if berlin_date != target_date:
                continue
            
            home_api = m['home_team']
            away_api = m['away_team']
            home_model = TEAM_MAP.get(home_api, home_api)
            away_model = TEAM_MAP.get(away_api, away_api)
            
            if home_model not in elos or away_model not in elos:
                continue
            
            home_elo = elos[home_model]['elo']
            away_elo = elos[away_model]['elo']
            elo_diff = home_elo - away_elo + 100
            home_prob = 1 / (1 + 10**(-elo_diff/400))
            
            for bm in m.get('bookmakers', [])[:1]:
                for market in bm.get('markets', []):
                    if market['key'] == 'h2h':
                        odds = {}
                        for o in market['outcomes']:
                            if o['name'] == home_api: odds['home'] = o['price']
                            elif o['name'] == away_api: odds['away'] = o['price']
                        
                        if 'home' in odds and 'away' in odds:
                            hv = home_prob - (1/odds['home'])
                            av = (1-home_prob) - (1/odds['away'])
                            
                            game_time = berlin_dt.strftime('%H:%M')
                            
                            if hv > 0.02:
                                value_bets.append({
                                    'time': game_time,
                                    'match': f"{home_api} vs {away_api}",
                                    'pick': home_api, 'type': 'HOME',
                                    'odds': odds['home'], 'prob': home_prob,
                                    'value': hv
                                })
                            if av > 0.02:
                                value_bets.append({
                                    'time': game_time,
                                    'match': f"{home_api} vs {away_api}",
                                    'pick': away_api, 'type': 'AWAY',
                                    'odds': odds['away'], 'prob': 1-home_prob,
                                    'value': av
                                })
    
    return value_bets

def save_to_tracking(bets, date):
    """Save bets to tracking database"""
    conn = sqlite3.connect('data/value_tracking.db')
    c = conn.cursor()
    
    added = 0
    for bet in bets:
        c.execute('''INSERT INTO bets (date, sport, league, match, pick, bet_type, odds, model_prob, value_pct)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (date, 'NBA', 'NBA', bet['match'], bet['pick'], bet['type'],
                   bet['odds'], bet['prob'], bet['value']))
        added += 1
    
    conn.commit()
    conn.close()
    return added

def main():
    print("🏀 NBA VALUE BET DETECTION (Berlin Time)")
    print("="*70)
    
    today_berlin = get_berlin_date()
    tomorrow_berlin = get_berlin_date(1)
    
    print(f"\n📅 Berlin Today: {today_berlin}")
    print(f"📅 Berlin Tomorrow: {tomorrow_berlin}")
    
    # Check if we already tracked for tomorrow (tonight's games)
    conn = sqlite3.connect('data/value_tracking.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bets WHERE date = ? AND sport = 'NBA'", (tomorrow_berlin,))
    already_tracked = c.fetchone()[0] > 0
    conn.close()
    
    if already_tracked:
        print(f"\n✓ Tomorrow's games ({tomorrow_berlin}) already tracked")
        return
    
    print(f"\n🔍 Detecting value bets for {tomorrow_berlin} (tonight's games)...")
    bets = detect_nba_value_bets(tomorrow_berlin)
    
    if bets:
        print(f"\n✅ Found {len(bets)} value bets:")
        for bet in bets:
            print(f"   {bet['time']} - {bet['match']}")
            print(f"      {bet['type']}: {bet['pick']} @ {bet['odds']:.2f} ({bet['value']:+.1%})")
        
        added = save_to_tracking(bets, tomorrow_berlin)
        print(f"\n💾 Saved {added} bets to tracking database")
    else:
        print(f"\n➖ No value bets found for {tomorrow_berlin}")

if __name__ == "__main__":
    main()

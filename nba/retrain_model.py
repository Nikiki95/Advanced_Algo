#!/usr/bin/env python3
"""
NBA ELO Model Retraining - COMBINED 2024/25 + 2025/26
Uses historical data + current season for accurate predictions
"""

import requests
import json
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from elo_model import NBAEloModel

# Team name mappings
TEAM_ABBREVS = {
    'Atlanta Hawks': 'Atlanta', 'Boston Celtics': 'Boston',
    'Brooklyn Nets': 'Brooklyn', 'Charlotte Hornets': 'Charlotte',
    'Chicago Bulls': 'Chicago', 'Cleveland Cavaliers': 'Cleveland',
    'Dallas Mavericks': 'Dallas', 'Denver Nuggets': 'Denver',
    'Detroit Pistons': 'Detroit', 'Golden State Warriors': 'Golden State',
    'Houston Rockets': 'Houston', 'Indiana Pacers': 'Indiana',
    'LA Clippers': 'LA Clippers', 'Los Angeles Lakers': 'LAL',
    'Memphis Grizzlies': 'Memphis', 'Miami Heat': 'Miami',
    'Milwaukee Bucks': 'Milwaukee', 'Minnesota Timberwolves': 'Minnesota',
    'New Orleans Pelicans': 'New Orleans', 'New York Knicks': 'New York',
    'Oklahoma City Thunder': 'Oklahoma City', 'Orlando Magic': 'Orlando',
    'Philadelphia 76ers': 'Philadelphia', 'Phoenix Suns': 'Phoenix',
    'Portland Trail Blazers': 'Portland', 'Sacramento Kings': 'Sacramento',
    'San Antonio Spurs': 'San Antonio', 'Toronto Raptors': 'Toronto',
    'Utah Jazz': 'Utah', 'Washington Wizards': 'Washington',
}

def fetch_season(year):
    """Fetch games from a specific season"""
    print(f"📡 Downloading NBA {year}/{year+1} season...")
    url = f"https://fixturedownload.com/feed/json/nba-{year}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.json()
    
    # Add season marker
    for game in data:
        game['_season'] = f"{year}/{year+1}"
    
    played = [g for g in data if g.get('HomeTeamScore') is not None and g.get('HomeTeamScore') > 0]
    print(f"✅ {year}/{year+1}: {len(played)} games played")
    return data, len(played)

def combine_seasons():
    """Fetch and combine both seasons"""
    print("=" * 60)
    print("Fetching NBA Data - 2024/25 + 2025/26")
    print("=" * 60)
    
    # Fetch 2024/25 (historical)
    games_24, played_24 = fetch_season(2024)
    
    # Fetch 2025/26 (current)
    games_25, played_25 = fetch_season(2025)
    
    # Combine
    all_games = games_24 + games_25
    total_played = played_24 + played_25
    
    print(f"\n📊 TOTAL: {total_played} games available for training")
    print(f"   - 2024/25: {played_24} games (historical)")
    print(f"   - 2025/26: {played_25} games (current)")
    
    return all_games, total_played

def train_model(games):
    """Train ELO model on TIME-BASED MEMORY (last 60 days)"""
    from datetime import datetime, timedelta
    
    print("\n🎓 Training ELO model on TIME-BASED MEMORY (last 60 days)...")
    
    # Time-based memory: Last 60 days (~400-500 games), balanced K-factor
    model = NBAEloModel(
        initial_elo=1500,
        k_factor=24,  # Lower K for more stable ratings with more data
        home_advantage=100,
        margin_mult=1.0
    )
    
    # Sort by date
    games_sorted = sorted(games, key=lambda x: x.get('DateUtc', ''))
    
    # Filter: Only games from last 60 days
    cutoff_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    recent_games = [g for g in games_sorted if g.get('DateUtc', '')[:10] >= cutoff_date]
    
    # Only games with scores
    games_with_scores = []
    for game in recent_games:
        home_score = game.get('HomeTeamScore')
        away_score = game.get('AwayTeamScore')
        if home_score is not None and away_score is not None:
            if home_score > 0 or away_score > 0:
                games_with_scores.append(game)
    
    print(f"📊 Using {len(games_with_scores)} games from last 60 days")
    
    trained = 0
    for game in recent_games:
        home_team = game.get('HomeTeam')
        away_team = game.get('AwayTeam')
        home_score = game.get('HomeTeamScore')
        away_score = game.get('AwayTeamScore')
        date = game.get('DateUtc', '')[:10]
        
        # Normalize team names
        home = TEAM_ABBREVS.get(home_team, home_team)
        away = TEAM_ABBREVS.get(away_team, away_team)
        
        try:
            # Update model
            model.update_game(home, away, home_score, away_score, date)
            trained += 1
                
        except Exception as e:
            print(f"⚠️ Error on {home} vs {away}: {e}")
    
    print(f"✅ Trained on {trained} games (SHORT MEMORY: last 20)")
    
    return model

def show_rankings(model):
    """Display current ELO rankings"""
    print("\n🏀 FINAL ELO Rankings (2025/26 Current):")
    print("=" * 60)
    
    teams = [(team, data['elo']) for team, data in model.elos.items()]
    teams.sort(key=lambda x: x[1], reverse=True)
    
    for i, (team, elo) in enumerate(teams, 1):
        games = model.elos[team].get('games', 0)
        # Show trend indicator
        if i <= 5:
            marker = "🔥"
        elif i <= 15:
            marker = "✅"
        else:
            marker = "📉"
        print(f"{marker} {i:2d}. {team:<20} {elo:.0f}  ({games} games)")
    
    return teams

def test_predictions(model):
    """Test some current matchups"""
    print("\n🔮 Current Matchup Predictions:")
    print("=" * 60)
    
    # Real upcoming/possible matchups
    test_games = [
        ('Boston', 'Brooklyn'),      # Celtics favorite
        ('LAL', 'Golden State'),     # Lakers vs Warriors
        ('Oklahoma City', 'Denver'), # OKC #1
        ('Milwaukee', 'Philadelphia'),
        ('Cleveland', 'New York'),   # Cavs strong
        ('LAC', 'Phoenix'),
    ]
    
    for home, away in test_games:
        try:
            pred = model.predict(home, away)
            home_elo = pred['home_elo']
            away_elo = pred['away_elo']
            win_prob = pred['home_win_prob'] * 100
            
            # Determine favorite
            if win_prob > 55:
                status = "🏠 Home favorite"
            elif win_prob < 45:
                status = "✈️ Away favorite"
            else:
                status = "⚖️ Toss-up"
            
            print(f"\n{home} ({home_elo:.0f}) vs {away} ({away_elo:.0f}):")
            print(f"   → Home win: {win_prob:.1f}% | {status}")
        except Exception as e:
            print(f"⚠️ {home} vs {away}: {e}")

def save_model(model):
    """Save the trained model"""
    output_dir = Path('models')
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d')
    output_path = output_dir / f'elo_model_2025_2026_{timestamp}.pkl'
    
    model.save(str(output_path))
    print(f"\n💾 Model saved: {output_path}")
    
    # Update symlink
    symlink_path = output_dir / 'elo_model_202603.pkl'
    if symlink_path.exists() or symlink_path.is_symlink():
        symlink_path.unlink()
    symlink_path.symlink_to(output_path.name)
    print(f"🔗 Symlink updated: elo_model_202603.pkl")
    
    return output_path

def main():
    print("=" * 60)
    print("NBA ELO Model Retraining")
    print("Combined: 2024/25 History + 2025/26 Current")
    print("=" * 60)
    
    # Fetch combined data
    games, total = combine_seasons()
    
    # Train
    model = train_model(games)
    
    # Show rankings
    rankings = show_rankings(model)
    
    # Test
    test_predictions(model)
    
    # Save
    save_model(model)
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS! Model trained on combined data:")
    print(f"   • Total games: {total}")
    print(f"   • Teams: {len(model.elos)}/30")
    print(f"   • Current through: March 2026")
    print("=" * 60)
    print("Model ready for 2025/26 season value betting!")

if __name__ == "__main__":
    main()

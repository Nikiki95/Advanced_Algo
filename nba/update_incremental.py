#!/usr/bin/env python3
"""
NBA Daily Incremental Updater
Fügt jeden Tag neue Spiele zum bestehenden Modell hinzu.
Statt: Alte Daten löschen → Neue 50 Spiele laden
Jetzt: Alte Daten behalten → Neue Spiele anhängen
"""

import sys
import pickle
import requests
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, 'src')
from elo_model import NBAEloModel

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

def load_existing_model():
    """Lade bestehendes Modell oder erstelle neues"""
    
    # 1. Prüfe inkrementelles Modell (bevorzugt)
    incremental_path = Path('models/elo_model_incremental.pkl')
    if incremental_path.exists():
        with open(incremental_path, 'rb') as f:
            data = pickle.load(f)
        total = sum(len(g) for g in data.get('games_per_team', {}).values())
        print(f"✅ Inkrementelles Modell geladen: {total} Spiele total")
        return data
    
    # 2. Versuche vom Standard-Modell zu migrieren (falls vorhanden)
    standard_path = Path('models/elo_model_202603.pkl')
    if standard_path.exists():
        try:
            with open(standard_path, 'rb') as f:
                std = pickle.load(f)
            if 'elos' in std and len(std['elos']) > 5:
                print(f"📥 Migration vom Standard-Modell: {len(std['elos'])} teams gefunden")
                # Erstelle games_per_team aus ELO-Daten (geschätzt)
                games_per_team = {}
                for team, data in std.get('elos', {}).items():
                    games = data.get('games', 1)
                    # Wir können die genauen Spiele nicht rekonstruieren, 
                    # aber wir merken uns, dass wir bereits Daten haben
                    games_per_team[team] = [{'migrated': True, 'games': games}]
                return {
                    'games_per_team': games_per_team,
                    'last_update': datetime.now().isoformat(),
                    'total_games': sum(d.get('games', 1) for d in std.get('elos', {}).values()),
                    'migrated_from_standard': True
                }
        except:
            pass
    
    # 3. Neues Modell erstellen
    print("🆕 Neues Modell wird erstellt")
    return {
        'games_per_team': {},
        'last_update': None,
        'total_games': 0
    }

def fetch_yesterday_games():
    """Hole gestrige NBA Spiele"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"📡 Suche Spiele vom {yesterday}...")
    
    # Versuche beide Saisons
    all_new_games = []
    
    for year in [2025, 2024]:
        url = f"https://fixturedownload.com/feed/json/nba-{year}"
        try:
            resp = requests.get(url, timeout=30)
            data = resp.json()
            
            for game in data:
                game_date = game.get('DateUtc', '')[:10]
                if game_date == yesterday:
                    home_score = game.get('HomeTeamScore')
                    away_score = game.get('AwayTeamScore')
                    
                    if home_score is not None and away_score is not None and home_score > 0:
                        all_new_games.append(game)
                        
        except Exception as e:
            print(f"⚠️ Fehler bei Saison {year}: {e}")
    
    print(f"✅ {len(all_new_games)} neue Spiele gefunden")
    return all_new_games

def update_model_incremental(existing_data, new_games):
    """Füge neue Spiele zum bestehenden Modell hinzu"""
    
    games_per_team = existing_data['games_per_team']
    
    for game in new_games:
        home = TEAM_ABBREVS.get(game['HomeTeam'], game['HomeTeam'])
        away = TEAM_ABBREVS.get(game['AwayTeam'], game['AwayTeam'])
        
        # Speichere für beide Teams
        game_data = {
            'date': game['DateUtc'],
            'home': home,
            'away': away,
            'home_score': game['HomeTeamScore'],
            'away_score': game['AwayTeamScore'],
            'processed': False
        }
        
        if home not in games_per_team:
            games_per_team[home] = []
        if away not in games_per_team:
            games_per_team[away] = []
        
        # Prüfe ob Spiel schon existiert
        exists = any(
            g['date'] == game_data['date'] and 
            g['home'] == game_data['home'] and 
            g['away'] == game_data['away']
            for g in games_per_team[home]
        )
        
        if not exists:
            games_per_team[home].append(game_data)
            games_per_team[away].append(game_data)
            existing_data['total_games'] += 1
    
    existing_data['last_update'] = datetime.now().isoformat()
    
    # Zeige Statistik
    print("\n📊 SPIELE PRO TEAM (inkrementell):")
    for team, games in sorted(games_per_team.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"   {team:20s}: {len(games):3d} Spiele")
    
    return existing_data

def train_elo_from_history(games_per_team, max_games_per_team=100):
    """Trainiere ELO mit allen gesammelten Spielen"""
    
    print(f"\n🎓 Training ELO mit Historie (max {max_games_per_team} Spiele pro Team)...")
    
    model = NBAEloModel(
        initial_elo=1500,
        k_factor=24,  # Konservativer als Short Memory
        home_advantage=100,
        margin_mult=1.0
    )
    
    # Sammle alle eindeutigen Spiele
    all_games = set()
    for team_games in games_per_team.values():
        for g in team_games:
            game_key = (g['date'], g['home'], g['away'])
            all_games.add((g['date'], g['home'], g['away'], g['home_score'], g['away_score']))
    
    # Sortiere nach Datum
    sorted_games = sorted(all_games, key=lambda x: x[0])
    
    print(f"📊 {len(sorted_games)} eindeutige Spiele zum Training")
    
    # Training
    for date, home, away, home_score, away_score in sorted_games:
        try:
            model.update_game(home, away, home_score, away_score, date)
        except Exception as e:
            pass  # Ignoriere Fehler für einzelne Spiele
    
    return model

def save_incremental_model(existing_data, elo_model):
    """Speichere inkrementelles Modell - Überschreibe Standard NIE mit weniger Daten!"""
    
    output = {
        'games_per_team': existing_data['games_per_team'],
        'total_games': existing_data['total_games'],
        'last_update': existing_data['last_update'],
        'elos': elo_model.elos if hasattr(elo_model, 'elos') else {},
        'history': elo_model.history if hasattr(elo_model, 'history') else []
    }
    
    # SPEICHERE INKREMENTELLES MODELL (Master)
    with open('models/elo_model_incremental.pkl', 'wb') as f:
        pickle.dump(output, f)
    
    # PRÜFE OB WIR DAS STANDARD-MODELL ÜBERSCHREIBEN SOLLTEN
    standard_path = Path('models/elo_model_202603.pkl')
    should_update_standard = True
    
    if standard_path.exists() and not standard_path.is_symlink():
        try:
            with open(standard_path, 'rb') as f:
                std = pickle.load(f)
            std_games = sum(d.get('games', 0) for d in std.get('elos', {}).values())
            new_games = sum(d.get('games', 0) for d in output['elos'].values())
            
            if new_games < std_games * 0.8:  # Wenn < 80% der Daten
                print(f"\n⚠️  WARNUNG: Inkrementelles Modell hat nur {new_games} Spiele")
                print(f"    Standard-Modell hat {std_games} Spiele")
                print(f"    Standard-Modell wird NICHT überschrieben!")
                should_update_standard = False
        except:
            pass
    
    # NUR WENN GENUG DATEN: Standard-Modell aktualisieren
    if should_update_standard:
        # Backup des alten Standard-Modells
        if standard_path.exists():
            backup_path = Path('models/elo_model_backup.pkl')
            try:
                with open(standard_path, 'rb') as f:
                    old = pickle.load(f)
                with open(backup_path, 'wb') as f:
                    pickle.dump(old, f)
            except:
                pass
        
        # Schreibe neues Standard-Modell
        with open(standard_path, 'wb') as f:
            pickle.dump({'elos': output['elos'], 'history': output['history']}, f)
        print(f"   ✅ Standard-Modell aktualisiert")
    
    print(f"\n💾 Gespeichert:")
    print(f"   - Inkrementell (Master): models/elo_model_incremental.pkl")
    print(f"   - Total Spiele: {existing_data['total_games']}")

def main():
    print("="*70)
    print("🏀 NBA INKREMENTELLES UPDATE")
    print("="*70)
    
    # 1. Lade bestehendes Modell
    existing_data = load_existing_model()
    
    # 2. Hole neue Spiele
    new_games = fetch_yesterday_games()
    
    if not new_games:
        print("\n➖ Keine neuen Spiele gefunden")
        return
    
    # 3. Füge zu bestehendem Modell hinzu
    updated_data = update_model_incremental(existing_data, new_games)
    
    # 4. Trainiere ELO mit gesamter Historie
    elo_model = train_elo_from_history(updated_data['games_per_team'])
    
    # 5. Speichere
    save_incremental_model(updated_data, elo_model)
    
    # 6. Zeige Top Teams
    print("\n🏆 TOP 10 TEAMS (nach inkrementellem Training):")
    if hasattr(elo_model, 'elos'):
        teams = [(t, d['elo'], d.get('games', 0)) for t, d in elo_model.elos.items()]
        teams.sort(key=lambda x: x[1], reverse=True)
        for i, (team, elo, games) in enumerate(teams[:10], 1):
            print(f"{i:2d}. {team:20s} {elo:4.0f} ({games} games)")
    
    print("\n" + "="*70)
    print("✅ Update abgeschlossen!")
    print("="*70)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Liga-spezifische Modell-Training
Trainiert separate Dixon-Coles Modelle für jede Top-Liga
"""
import sys
import pickle
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config
from data.loader import FootballDataLoader
from model.dixon_coles import DixonColesModel


# League Konfiguration für football-data.co.uk
LEAGUE_CONFIG = {
    # Deutschland
    'D1': {'name': 'Bundesliga', 'country': 'Germany', 'seasons': 3},
    'D2': {'name': '2. Bundesliga', 'country': 'Germany', 'seasons': 3},
    
    # England  
    'E0': {'name': 'Premier League', 'country': 'England', 'seasons': 3},
    'E1': {'name': 'Championship', 'country': 'England', 'seasons': 3},
    
    # Spanien
    'SP1': {'name': 'La Liga', 'country': 'Spain', 'seasons': 3},
    
    # Italien
    'I1': {'name': 'Serie A', 'country': 'Italy', 'seasons': 3},
    
    # Frankreich
    'F1': {'name': 'Ligue 1', 'country': 'France', 'seasons': 3},
    
    # Portugal
    'P1': {'name': 'Primeira Liga', 'country': 'Portugal', 'seasons': 3},
    
    # Niederlande
    'N1': {'name': 'Eredivisie', 'country': 'Netherlands', 'seasons': 3},
}


class LeagueModelTrainer:
    """Trainiert liga-spezifische Modelle"""
    
    def __init__(self):
        self.data_loader = FootballDataLoader()
        self.models_dir = Path("models/leagues")
        self.models_dir.mkdir(parents=True, exist_ok=True)
    
    def train_league(self, league_code: str, force_retrain: bool = False):
        """Trainiert ein Modell für eine spezifische Liga"""
        
        if league_code not in LEAGUE_CONFIG:
            print(f"❌ Unbekannte Liga: {league_code}")
            return None
        
        config_league = LEAGUE_CONFIG[league_code]
        model_path = self.models_dir / f"dixon_coles_{league_code}.pkl"
        
        print(f"\n{'='*60}")
        print(f"🏆 Training: {config_league['name']}")
        print(f"{'='*60}")
        
        # Prüfe ob existiert
        if model_path.exists() and not force_retrain:
            print(f"✅ Modell existiert bereits: {model_path}")
            print(f"   Lade...")
            return DixonColesModel.load(model_path)
        
        # Lade Daten
        print(f"\n📊 Lade historische Daten...")
        try:
            df = self._load_league_data(league_code, config_league['seasons'])
        except Exception as e:
            print(f"❌ Fehler beim Laden: {e}")
            print(f"   Möglicherweise hat football-data keine Daten für {league_code}")
            return None
        
        if len(df) < 50:
            print(f"❌ Zu wenig Daten: {len(df)} Spiele")
            return None
        
        print(f"✅ {len(df)} Spiele geladen")
        
        # Trainiere Modell
        print(f"\n🧠 Training Dixon-Coles Modell...")
        model = DixonColesModel(rho=config.DC_RHO)
        model.fit(df)
        
        # Speichere
        model.save(model_path)
        
        print(f"✅ Modell gespeichert: {model_path}")
        print(f"   Teams: {len(model.team_ratings)}")
        
        return model
    
    def _load_league_data(self, league_code: str, seasons: int) -> pd.DataFrame:
        """Lädt Daten für eine Liga"""
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Saison-Logik
        if current_month < 8:
            season_start = current_year - 1
        else:
            season_start = current_year
        
        all_data = []
        
        for year_offset in range(seasons):
            year = season_start - year_offset
            print(f"   Lade Saison {year}/{year+1}...", end=' ')
            
            try:
                df = self.data_loader.download_season(league_code, year)
                if not df.empty:
                    df = self.data_loader.process_match_data(df)
                    df['League'] = league_code
                    df['Season'] = f"{year}/{year+1}"
                    all_data.append(df)
                    print(f"✅ {len(df)} Spiele")
                else:
                    print("⚠️  Keine Daten")
            except Exception as e:
                print(f"❌ {e}")
        
        if not all_data:
            return pd.DataFrame()
        
        return pd.concat(all_data, ignore_index=True)
    
    def train_all(self, force_retrain: bool = False):
        """Trainiert alle verfügbaren Ligen"""
        print("🚀 Training ALLER Liga-Modelle")
        print(f"Ziel: {len(LEAGUE_CONFIG)} Ligen\n")
        
        results = {}
        
        for league_code in LEAGUE_CONFIG.keys():
            model = self.train_league(league_code, force_retrain)
            results[league_code] = model is not None
        
        # Summary
        print(f"\n{'='*60}")
        print("📊 TRAINING ZUSAMMENFASSUNG")
        print(f"{'='*60}")
        
        for code, success in results.items():
            name = LEAGUE_CONFIG[code]['name']
            status = "✅" if success else "❌"
            print(f"{status} {code:6s} - {name}")
        
        successful = sum(results.values())
        print(f"\nErfolgreich: {successful}/{len(results)} Ligen")
        
        return results
    
    def list_available(self):
        """Zeigt verfügbare Ligen"""
        print("Verfügbare Ligen für Training:")
        print("-" * 60)
        
        for code, info in LEAGUE_CONFIG.items():
            model_path = self.models_dir / f"dixon_coles_{code}.pkl"
            exists = "✅ Vorhanden" if model_path.exists() else "❌ Nicht trainiert"
            print(f"{code:6s} - {info['name']:20s} ({info['country']}) {exists}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Trainiere Liga-spezifische Modelle")
    parser.add_argument('--league', choices=list(LEAGUE_CONFIG.keys()),
                       help='Spezifische Liga trainieren')
    parser.add_argument('--all', action='store_true',
                       help='Alle Ligen trainieren')
    parser.add_argument('--list', action='store_true',
                       help='Verfügbare Ligen anzeigen')
    parser.add_argument('--force', action='store_true',
                       help='Neu trainieren auch wenn vorhanden')
    
    args = parser.parse_args()
    
    trainer = LeagueModelTrainer()
    
    if args.list:
        trainer.list_available()
    elif args.all:
        trainer.train_all(force_retrain=args.force)
    elif args.league:
        trainer.train_league(args.league, force_retrain=args.force)
    else:
        print("Verwende: --list, --all, oder --league CODE")
        print(f"\nBeispiele:")
        print(f"  ./venv/bin/python {__file__} --list")
        print(f"  ./venv/bin/python {__file__} --league E0")
        print(f"  ./venv/bin/python {__file__} --all")


if __name__ == "__main__":
    main()
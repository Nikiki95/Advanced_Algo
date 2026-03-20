#!/usr/bin/env python3
"""
NBA Betting Analyzer
Hauptskript für: Training → Odds → Value-Bets → Alerts
"""

import sys
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Setup paths
sys.path.insert(0, str(Path(__file__).parent / "src"))

from elo_model import NBAEloModel
from odds_scraper import NBAOddsScraper
from value_engine import NBAValueEngine
from data_loader import NBALoader
from nba_context import NBAContextScraper
from config import MODELS_DIR, DATA_DIR

# Telegram Integration
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "football" / "src"))
    from notifications.telegram import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    TelegramNotifier = None

def train_model(days_back: int = 90, save: bool = True, max_games: int = 30) -> NBAEloModel:
    """
    Trainiert ELO-Modell auf historischen Daten.
    
    Args:
        days_back: Wie viele Tage zurück trainieren
        save: Modell speichern?
    """
    print(f"🔄 Training ELO-Modell (letzte {days_back} Tage)...")
    
    loader = NBALoader()
    games = loader.fetch_games(days_back=days_back)
    
    if len(games) == 0:
        print("⚠️  Keine Trainingsdaten verfügbar")
        return None
    
    model = NBAEloModel(
        initial_elo=1500,
        k_factor=20,
        home_advantage=100,
        margin_mult=1.0
    )
    
    model.train(games, max_games=max_games)
    
    if save:
        model_path = MODELS_DIR / f"elo_model_{datetime.now().strftime('%Y%m')}.pkl"
        model.save(str(model_path))
    
    print(f"✅ Training complete!")
    print(f"   Teams: {len(model.elos)}")
    print(f"   Spiele: {len(games)}")
    print("\n📊 Top 5 nach ELO:")
    rankings = model.get_rankings().head(5)
    for _, row in rankings.iterrows():
        print(f"   {row['rank']}. {row['team']}: {row['elo']:.0f}")
    
    return model


def find_value_bets(model: NBAEloModel, min_value: float = 0.05, 
                    use_context: bool = True) -> tuple:
    """
    Holt aktuelle Odds und findet Value-Bets.
    Mit optionaler Context-Anpassung (Injuries, Fatigue, Load Mgmt).
    
    Args:
        model: Trainiertes ELO-Modell
        min_value: Mindest-Edge (5% = 0.05)
        use_context: Context-Scraper aktivieren?
    
    Returns:
        (DataFrame mit Bets, Dict mit Context-Info)
    """
    context_info = {}
    
    # Context Scraper initialisieren
    context_scraper = None
    if use_context:
        try:
            from nba_context import NBAContextScraper
            context_scraper = NBAContextScraper()
            print("📊 Context Scraper aktiviert (Injuries, Fatigue, Load Mgmt)")
        except Exception as e:
            print(f"⚠️ Context Scraper nicht verfügbar: {e}")
    
    return _find_value_bets_internal(model, min_value, context_scraper), context_info

def _find_value_bets_internal(model: NBAEloModel, min_value: float = 0.05,
                               context_scraper=None) -> pd.DataFrame:
    """
    Holt aktuelle Odds und findet Value-Bets.
    
    Args:
        model: Trainiertes ELO-Modell
        min_value: Mindest-Edge (5% = 0.05)
    """
    print(f"\n🔍 Suche nach Value-Bets (min {min_value*100:.0f}% Edge)...")
    
    # Scrape Odds
    scraper = NBAOddsScraper()
    odds = scraper.fetch_upcoming(days=3)
    
    if len(odds) == 0:
        print("⚠️  Keine Odds verfügbar")
        return pd.DataFrame()
    
    print(f"   {len(odds)} Spiele gefunden mit Odds")
    
    # Value Engine
    engine = NBAValueEngine(
        value_threshold=min_value,
        kelly_fraction=0.25,
        bankroll=1000.0
    )
    
    all_bets = []
    
    for _, game in odds.iterrows():
        home_team = game["home_team"]
        away_team = game["away_team"]
        
        # Modell-Vorhersagen
        predictions = model.predict(home_team, away_team)
        
        # Erweiterte Vorhersagen für Spreads/Totals
        model_preds = {
            "home_win_prob": predictions["home_win_prob"],
            "away_win_prob": predictions["away_win_prob"],
            # Spread: Annäherung über Elo-Differenz
            "home_cover_prob": min(0.75, max(0.25, 
                0.5 + (predictions["elo_diff"] / 400) * 0.3)),
            "over_prob": 0.5,  # TODO: Punkte-Modell
        }
        
        # Analysiere alle Märkte
        game_bets = engine.analyze_game(
            game_id=game.get("game_id", "unknown"),
            home_team=home_team,
            away_team=away_team,
            odds_data=game.to_dict(),
            model_predictions=model_preds
        )
        
        all_bets.extend(game_bets)
    
    # Filtere beste
    best_bets = engine.get_best_bets(all_bets, min_confidence="medium", max_bets=20)
    
    return engine.to_dataframe(best_bets)


def send_telegram_alerts(df: pd.DataFrame):
    """Sendet NBA Value-Bets via Telegram."""
    if not TELEGRAM_AVAILABLE or df.empty:
        return
    
    notifier = TelegramNotifier()
    if not notifier.is_configured():
        print("⚠️  Telegram nicht konfiguriert")
        return
    
    print(f"📱 Sende {len(df)} Alerts...")
    sent = 0
    
    for _, row in df.iterrows():
        # Extrahiere Teams aus selection wenn nicht separat vorhanden
        selection = row['selection']
        if ' @ ' in selection or ' vs ' in selection:
            match = selection.split(' @ ')[0] if ' @ ' in selection else selection.split(' vs ')[0]
        else:
            match = selection
        
        bet_data = {
            'match': match,
            'market': row['market'],
            'selection': selection,
            'odds': row['odds'],
            'model_prob': row['model_prob'],
            'value': row['value'] / 100 if row['value'] > 1 else row['value'],
            'kelly': row['kelly'],
            'bet_size': row['bet_size'],
            'confidence': row['confidence'],
        }
        if notifier.sync_send_nba_alert(bet_data):
            sent += 1
    
    print(f"✅ {sent}/{len(df)} Alerts gesendet")


def display_bets(df: pd.DataFrame):
    """Zeigt Value-Bets schön formatiert an."""
    if df.empty:
        print("\n❌ Keine Value-Bets gefunden")
        return
    
    print(f"\n{'='*70}")
    print(f"🎯 NBA VALUE BETS GEFUNDEN: {len(df)}")
    print(f"{'='*70}")
    
    for i, row in df.iterrows():
        print(f"\n{i+1}. {row['selection']}")
        print(f"   Markt: {row['market'].upper()}")
        print(f"   Quote: {row['odds']:.2f}")
        print(f"   Modell-Wahrscheinlichkeit: {row['model_prob']*100:.1f}%")
        print(f"   ⭐ EDGE: +{row['value']:.1f}%")
        print(f"   Kelly: {row['kelly']:.1%}")
        print(f"   Einsatz: ${row['bet_size']:.2f}")
        print(f"   Konfidenz: {row['confidence'].upper()}")
    
    print(f"\n{'='*70}")


def main():
    parser = argparse.ArgumentParser(description="NBA Betting Analyzer")
    parser.add_argument("--train", action="store_true", help="Modell neu trainieren")
    parser.add_argument("--days-back", type=int, default=90, help="Trainings-Tage")
    parser.add_argument("--min-value", type=float, default=0.05, help="Min Edge (0.05 = 5%)")
    parser.add_argument("--model-path", type=str, help="Pfad zu geladenem Modell")
    
    args = parser.parse_args()
    
    print("="*70)
    print("🏀 NBA BETTING ANALYZER")
    print("="*70)
    
    # Modell laden oder trainieren
    if args.train:
        model = train_model(days_back=args.days_back)
    elif args.model_path:
        print(f"🔄 Lade Modell: {args.model_path}")
        model = NBAEloModel.load(args.model_path)
    else:
        # Versuche neuestes Modell zu laden
        import glob
        model_files = sorted(MODELS_DIR.glob("elo_model_*.pkl"))
        if model_files:
            latest = model_files[-1]
            print(f"🔄 Lade neuestes Modell: {latest.name}")
            model = NBAEloModel.load(str(latest))
        else:
            print("Kein Modell gefunden. Starte Training...")
            model = train_model(days_back=args.days_back)
    
    if model is None:
        print("❌ Fehler: Kein Modell verfügbar")
        sys.exit(1)
    
    # Value-Bets finden
    bets = find_value_bets(model, min_value=args.min_value)
    display_bets(bets)
    
    # Telegram Alerts
    if not bets.empty:
        send_telegram_alerts(bets)
    
    # Speichern
    if not bets.empty:
        output_path = DATA_DIR / f"value_bets_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        bets.to_csv(output_path, index=False)
        print(f"\n💾 Gespeichert: {output_path}")
    
    print("\n✅ Fertig!")


if __name__ == "__main__":
    main()

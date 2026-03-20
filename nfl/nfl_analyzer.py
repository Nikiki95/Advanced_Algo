#!/usr/bin/env python3
"""
NFL Betting Analyzer
"""

import sys
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))

from power_rank_model import NFLPowerModel
from odds_scraper import NFLOddsScraper
from value_engine import NFLValueEngine
from data_loader import NFLLoader
from config import MODELS_DIR, DATA_DIR

# Telegram Integration
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "football" / "src"))
    from notifications.telegram import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    TelegramNotifier = None


def train_model(weeks_back: int = 17):
    """Trainiert NFL Power Model."""
    print(f"🏈 Training NFL Power Model (letzte {weeks_back} Wochen)...")
    
    loader = NFLLoader()
    games = loader.fetch_games(weeks_back=weeks_back)
    
    if len(games) == 0:
        print("⚠️ Keine Trainingsdaten")
        return None
    
    model = NFLPowerModel(home_advantage=2.5, inter_season_regression=0.3)
    model.train(games, max_weeks=17)
    
    model_path = MODELS_DIR / f"nfl_power_{datetime.now().strftime('%Y%m')}.pkl"
    model.save(str(model_path))
    
    print(f"✅ Training complete! Teams: {len(model.power_scores)}")
    print("\n📊 Top 5 Power Rankings:")
    rankings = model.get_rankings().head(5)
    for _, row in rankings.iterrows():
        print(f"   {row['rank']}. {row['team']}: {row['power']:+.1f}")
    
    return model


def find_value_bets(model: NFLPowerModel, min_value: float = 0.04):
    """Findet NFL Value-Bets (Fokus auf Spread)."""
    print(f"\n🔍 Suche NFL Value-Bets (min {min_value*100:.0f}% Edge)...")
    
    scraper = NFLOddsScraper()
    odds = scraper.fetch_upcoming()
    
    if len(odds) == 0:
        print("⚠️ Keine Odds verfügbar")
        return pd.DataFrame()
    
    print(f"   {len(odds)} Spiele gefunden")
    
    engine = NFLValueEngine(
        value_threshold=min_value,
        kelly_fraction=0.25,
        bankroll=1000.0
    )
    
    all_bets = []
    
    for _, game in odds.iterrows():
        home = game["home_team"]
        away = game["away_team"]
        
        # Power-Ranking Vorhersagen
        preds = model.predict_spread(home, away)
        
        # Moneyline
        ml_bets = engine.evaluate_moneyline(
            game.get("game_id", "?"), home, away,
            game.get("home_odds"), game.get("away_odds"),
            preds["home_win_prob"]
        )
        all_bets.extend(ml_bets)
        
        # Spread (Hauptmarkt)
        spread_bets = engine.evaluate_spread(
            game.get("game_id", "?"), home, away,
            game.get("spread", 0), game.get("home_odds"), game.get("away_odds"),
            preds["home_cover_prob"]
        )
        all_bets.extend(spread_bets)
    
    # Filtere beste
    best = [b for b in all_bets if b.confidence in ["high", "medium"]]
    best = sorted(best, key=lambda x: x.value, reverse=True)[:15]
    
    return engine.to_dataframe(best)


def send_telegram_alerts(df: pd.DataFrame):
    """Sendet NFL Value-Bets via Telegram."""
    if not TELEGRAM_AVAILABLE or df.empty:
        return
    
    notifier = TelegramNotifier()
    if not notifier.is_configured():
        print("⚠️  Telegram nicht konfiguriert")
        return
    
    print(f"📱 Sende {len(df)} NFL Alerts...")
    sent = 0
    
    for _, row in df.iterrows():
        bet_data = {
            'match': row.get('selection', '?').split()[0] + ' vs ' + '?',  # Simplified
            'market': row['market'],
            'selection': row['selection'],
            'odds': row['odds'],
            'value': row['value%'] / 100,
            'bet_size': row['bet_size'],
            'confidence': row['conf'],
        }
        if notifier.sync_send_nfl_alert(bet_data):
            sent += 1
    
    print(f"✅ {sent}/{len(df)} Alerts gesendet")


def display_bets(df: pd.DataFrame):
    """Zeigt NFL Value-Bets."""
    if df.empty:
        print("\n❌ Keine Value-Bets gefunden")
        return
    
    print(f"\n{'='*70}")
    print(f"🏈 NFL VALUE BETS: {len(df)}")
    print(f"{'='*70}")
    
    for i, row in df.iterrows():
        print(f"\n{i+1}. {row['selection']}")
        print(f"   Markt: {row['market'].upper()}")
        print(f"   Quote: {row['odds']:.2f}")
        print(f"   Modell: {row['model_prob']*100:.1f}%")
        print(f"   ⭐ EDGE: +{row['value%']:.1f}%")
        print(f"   Kelly: {row['kelly']:.1%} | Einsatz: ${row['bet_size']:.2f}")


def main():
    parser = argparse.ArgumentParser(description="NFL Betting Analyzer")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--weeks-back", type=int, default=8)
    parser.add_argument("--min-value", type=float, default=0.04)
    
    args = parser.parse_args()
    
    print("="*70)
    print("🏈 NFL BETTING ANALYZER")
    print("="*70)
    
    # Modell laden oder trainieren
    if args.train:
        model = train_model(weeks_back=args.weeks_back)
    else:
        import glob
        model_files = sorted(MODELS_DIR.glob("nfl_power_*.pkl"))
        if model_files:
            print(f"🔄 Lade: {model_files[-1].name}")
            model = NFLPowerModel.load(str(model_files[-1]))
        else:
            print("Kein Modell gefunden. Starte Training...")
            model = train_model(weeks_back=args.weeks_back)
    
    if model is None:
        print("❌ Fehler")
        sys.exit(1)
    
    # Value-Bets
    bets = find_value_bets(model, min_value=args.min_value)
    display_bets(bets)
    
    # Telegram Alerts
    if not bets.empty:
        send_telegram_alerts(bets)
    
    if not bets.empty:
        output = DATA_DIR / f"nfl_value_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        bets.to_csv(output, index=False)
        print(f"\n💾 Gespeichert: {output}")
    
    print("\n✅ Fertig!")


if __name__ == "__main__":
    main()

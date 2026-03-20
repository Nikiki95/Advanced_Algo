# 🎯 Value-Bet Algorithm für Bundesliga

Kombination aus **Dixon-Coles Modell**, **SBR Odds-Scraping** und **Kelly-Kriterium** zur automatischen Value-Erkennung.

---

## 🚀 Quick Start

```bash
# 1. In den Ordner wechseln
cd betting-algorithm

# 2. Virtuelle Umgebung
cd betting-algorithm
cd betting-algorithm
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Config anpassen (optional)
cp .env.example .env
# .env bearbeiten mit Telegram Token

# 5. Erster Testlauf
python main.py --no-notify
```

---

## 📁 Projektstruktur

```
betting-algorithm/
├── main.py                 # CLI Entry Point
├── config.py               # Konfiguration
├── requirements.txt        # Dependencies
├── src/
│   ├── data/
│   │   └── loader.py       # football-data.co.uk Downloader
│   ├── model/
│   │   └── dixon_coles.py  # Dixon-Coles Modell
│   ├── scraper/
│   │   └── sbr_scraper.py  # SBR Odds Scraping
│   ├── engine/
│   │   └── value_engine.py # Value-Erkennung
│   └── notifications/
│       └── telegram.py     # Telegram Alerts
├── data/                   # Heruntergeladene Daten
└── models/                 # Trainierte Modelle
```

---

## ⚙️ Konfiguration (.env)

```bash
# Optional: Telegram für Alerts
TELEGRAM_BOT_TOKEN=dein_token_hier
TELEGRAM_CHAT_ID=deine_chat_id

# Value-Thresholds
MIN_VALUE_THRESHOLD=0.05      # 5% Mindest-Value
KELLY_FRACTION=0.25           # Quarter-Kelly

# Modell
TRAINING_YEARS=3              # Trainingshistorie
ODDS_UPDATE_INTERVAL_MIN=30   # Update-Intervall
```

---

## 🎮 Nutzung

```bash
# Modell trainieren
python main.py --train

# Value-Bets für Bundesliga finden
python main.py --league bundesliga

# Andere Ligen
python main.py --league premier-league
python main.py --league la-liga

# Test ohne Benachrichtigungen
python main.py --no-notify

# Telegram Test
python main.py --test-telegram
```

---

## 📊 Algorithmus-Workflow

```
1. DATEN        → Lade letzte 3 Jahre von football-data.co.uk
2. MODELL       → Trainiere Dixon-Coles mit Time-Weighting
3. FIXTURES     → Scrape kommende Matches von SBR
4. VORHERSAGE   → Berechne Wahrscheinlichkeiten pro Match
5. ODDS         → Hole aktuelle Bookmaker-Quoten
6. VALUE        → Vergleiche Modell vs. Market
7. ALERT        → Benachrichtige bei Value > Threshold
```

---

## 🧠 Dixon-Coles Modell

Erweitert das Standard-Poisson-Modell um:
- **ρ (Rho)**: Korrektur für niedrige Ergebnisse (0:0, 1:0, 0:1, 1:1)
- **Time-Decay**: Neue Spiele gewichten mehr
- **Team-Spezifisch**: Attack/Defense Ratings pro Team

Formel:
```
τ(λ, μ, ρ) = 1 - λμρ    (für 0:0, 1:0, 0:1, 1:1)
P(X=x, Y=y) = τ * Poisson(x, λ) * Poisson(y, μ)  (für niedrige Scores)
```

---

## 💰 Value-Berechnung

```
Market Prob = 1 / Bookmaker Odds
Value = Model Prob - Market Prob

Bet wenn: Value > MIN_VALUE_THRESHOLD (default: 5%)

Stake = Kelly Criterion * KELLY_FRACTION
Kelly = (bp - q) / b
  b = Odds - 1
  p = Model Probability
  q = 1 - p
```

---

## ⚠️ Wichtige Hinweise

- **Keine automatische Platzierung** – Alerts nur zur Information
- **SBR blockt manchmal** – Rate-Limiting integriert
- **Modell = kein Garant** – nur statistische Vorteile
- **Paper-Trading empfohlen** – erst testen, dann wetten

---

## 🔗 Datenquellen

| Quelle | URL | Nutzen |
|--------|-----|--------|
| football-data.co.uk | Free CSVs | Historische Ergebnisse |
| SBR (sbrscrape) | Free | Live Odds aller Bookies |
| penaltyblog | Open Source | DC-Modell Implementierung |

---

## 📈 Erfolgsmessung

Die Logs speichern:
- Alle Value-Bets mit Timestamp
- Model-Prob vs. Actual Outcome
- ROI pro Wette

```python
# CSV Export:
python main.py --export-csv
```

---

Lizenz: MIT | Keine Garantie für Gewinne 🎲

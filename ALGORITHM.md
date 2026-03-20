# 🎯 Betting Algorithm Suite v2 — Changelog & Status

**Stand:** 20. März 2026
**Version:** 2.0
**Projekte:** Fußball ✅ | NBA ✅ | NFL ✅

---

## 🆕 V2 ÄNDERUNGEN

### 🏗 Architektur

| Vorher | Nachher |
|--------|---------|
| 3 verschiedene Config-Systeme | **Unified Pydantic Config** (`shared/config.py`) |
| Feedback Loop nur Football | **Universal Feedback Loop** für alle Sportarten |
| Kein CLV-Tracking | **Closing Line Value** Analyse |
| Statische Confidence-Thresholds | **Bayesian Confidence** (kalibriert aus History) |
| NFL Mock-Daten in Odds-Scraper | **Echter TheOddsAPI Client** |

### ⚽ Football — Neue Features

| Feature | Status | Beschreibung |
|---------|--------|-------------|
| **Over/Under Engine** | ✅ | Poisson-basiert aus Expected Goals |
| **Double Chance** | ✅ | 1X, X2, 12 — abgeleitet oder direkt |
| **Korrelierte Bets** | ✅ | Erkennt Home+Over, Draw+Under Muster |
| **CLV Tracking** | ✅ | Opening Odds gespeichert, CLV berechnet |
| **Bayesian Confidence** | ✅ | Thresholds aus Feedback-Daten kalibriert |
| **TheOddsAPI h2h+totals** | ✅ | Beide Märkte in einem API-Call |

### 🏀 NBA — Fixes & Features

| Fix/Feature | Details |
|-------------|---------|
| **Training Window** | 150 Spiele statt 30 (≈ volle Saison) |
| **Season Regression** | Korrekt an Saisongrenzen angewendet |
| **Totals Model** | Pace-adjusted: ORtg × DRtg × Pace |
| **Spread Probability** | Elo → Expected Margin → Normal CDF |
| **Injury Adjustment** | Feature Flag `True` (war `False`) |

### 🏈 NFL — Fixes & Features

| Fix/Feature | Details |
|-------------|---------|
| **Regression nur zwischen Saisons** | War jedes Spiel, jetzt nur Season-Boundary |
| **Training Window** | 17 Wochen (volle Regular Season, war 8) |
| **Totals Model** | PPG/PAPG-basiert mit Home Advantage |
| **Echter Odds Scraper** | TheOddsAPI mit 32-Team Mapping |

---

## 📊 ARCHITEKTUR

```
betting-algorithm/
├── shared/                    # 📁 Gemeinsame Module
│   ├── config.py              # 🆕 Unified Pydantic Config
│   ├── feedback_loop.py       # 🆕 Universal Tracker + CLV + Bayesian
│   ├── telegram_bot.py        # 🆕 v2 CLV-Alerts + Korrelationen
│   ├── research_cron.py       # Context-Daten Sammler
│   └── api_sports_client.py
├── football/
│   ├── config.py              # Wrapper → shared/config.py
│   ├── src/engine/value_engine.py  # 🆕 1X2+DC+O/U+CLV+Bayesian
│   ├── src/scraper/theoddsapi.py   # 🆕 h2h+totals
│   └── feedback_loop.py            # 🔄 → shared
├── nba/
│   ├── config.py              # Wrapper → shared/config.py
│   ├── src/elo_model.py       # 🆕 Regression+Totals+Spread
│   └── src/value_engine.py    # 🆕 Alle Märkte+CLV
├── nfl/
│   ├── config.py              # Wrapper → shared/config.py
│   ├── src/power_rank_model.py # 🆕 Regression-Fix+Totals
│   ├── src/value_engine.py    # 🆕 Spread+ML+Totals+CLV
│   └── src/odds_scraper.py    # 🆕 Echter TheOddsAPI Client
├── secrets/.env               # API Keys (NIE committen!)
└── ALGORITHM.md
```

---

## 🔑 KONFIGURATION

```bash
# secrets/.env
THEODDS_API_KEY=dein_key_hier
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

| Parameter | Football | NBA | NFL |
|-----------|----------|-----|-----|
| Value Threshold (1X2/ML) | 5% | 5% | 6% |
| Value Threshold (Spread) | — | 3% | 4% |
| Value Threshold (O/U) | 4% | 4% | 5% |
| Value Threshold (DC) | 3% | — | — |
| Kelly Fraction | 25% | 25% | 25% |
| Training Window | 3 Jahre | 150 Spiele | 17 Wochen |

---

## 📈 CLV (Closing Line Value)

Zuverlässigster Indikator für langfristige Profitabilität.

1. Bet-Platzierung: Opening Odds + Timestamp gespeichert
2. Vor Kickoff: Closing Odds geholt
3. CLV: `(1/opening - 1/closing) / (1/closing)`

| CLV | Bedeutung |
|-----|-----------|
| > +3% | EXCELLENT |
| +1% bis +3% | GOOD |
| -1% bis +1% | NEUTRAL |
| < -1% | CONCERNING |

---

## 🧠 Bayesian Confidence

Confidence-Schwellenwerte passen sich automatisch an:
- Performance gut → Thresholds senken → Mehr Bets
- Performance schlecht → Thresholds erhöhen → Nur High-Value

Export: `python -m shared.feedback_loop` → `bayesian_export.json`

---

## 🔗 Korrelierte Bets (Football)

| Muster | Interpretation | Stärke |
|--------|---------------|--------|
| Home Win + Over | Dominanter Heimsieg | Strong |
| Away Win + Over | Offenes Spiel | Moderate |
| Draw + Under | Defensives Patt | Strong |

---

## 🚀 USAGE

```bash
# Tägliche Checks
cd football && python multi_league.py --leagues bundesliga epl
cd ../nba && python nba_analyzer.py
cd ../nfl && python nfl_analyzer.py

# Feedback Loop (alle Sportarten)
python -m shared.feedback_loop --sport all

# Weekly Retrain
cd football && python feedback_loop.py --weekly-retrain
```

---

**GitHub:** https://github.com/Nikiki95/betting-algorithm
**Version:** 2.0 — 20. März 2026

---

## 🆕 V2.1 MODEL IMPROVEMENTS

### 1. xG-basiertes Training (Football)

**Datei:** `football/src/data/xg_fetcher.py` + `football/src/model/dixon_coles.py`

Das Dixon-Coles-Modell trainiert jetzt auf **Expected Goals (xG)** statt auf tatsächlichen Toren. xG misst die Qualität der Torchancen und ist deutlich stabiler als reale Ergebnisse (ein Elfmeter in der 90. verzerrt Tore, nicht aber xG).

**Datenquellen (Priorität):**
1. football-data.co.uk (xG-Spalten in neueren CSVs)
2. Understat (6 Top-Ligen, JSON, kein API-Key)
3. Fallback: tatsächliche Tore

**Zusätzlich:**
- **Adaptiver Decay pro Liga**: Bundesliga (0.005), Premier League (0.003), 2. Bundesliga (0.006)
- **Aufsteiger-Handling**: Promoted Teams bekommen 15% Abschlag auf die Durchschnittsratings
- **Dixon-Coles Korrektur** für niedrige Ergebnisse (Rho-Parameter) auch im Poisson-Fallback

```bash
# Training mit xG
from model.dixon_coles import DixonColesModel
from data.xg_fetcher import XGDataFetcher

fetcher = XGDataFetcher()
data = fetcher.fetch_training_data('D1', seasons=3, prefer_xg=True)

model = DixonColesModel(training_mode='xg', league_code='D1')
model.fit(data, promoted_teams=['Holstein Kiel'])
```

### 2. Walk-Forward Backtesting

**Datei:** `shared/backtesting.py`

Erstmals systematisches Out-of-Sample-Testing. Walk-Forward bedeutet:
1. Trainiere auf Daten bis Tag T
2. Vorhersage für Spieltag T+1
3. Evaluiere gegen echte Ergebnisse
4. Schiebe Fenster vor, wiederhole

**Metriken:**
- Win-Rate, ROI, Profit
- Sharpe Ratio (risikoadjustierte Rendite)
- Kalibrierung (vorhergesagte vs. tatsächliche Wahrscheinlichkeit)
- Markt-Aufschlüsselung (1X2, O/U getrennt)

```bash
from shared.backtesting import create_football_backtester

bt = create_football_backtester(training_mode='xg', value_threshold=0.05)
data = xg_fetcher.fetch_training_data('D1', seasons=3)
result = bt.run(data, train_window_days=365, step_days=7)
print(result.summary())
```

**Modelle vergleichen:**
```bash
from shared.backtesting import compare_backtests
print(compare_backtests(result_xg, result_goals, result_with_prior))
```

### 3. Market Prior Integration

**Datei:** `shared/market_prior.py`

Statt das Modell komplett gegen den Markt zu stellen, kombinieren wir beides:

```
posterior = alpha × model + (1 - alpha) × market
```

- **alpha = 0.40** (Default für Football): Modell bekommt 40% Gewicht
- **alpha aus CLV kalibriert**: Positives CLV → alpha steigt (bis 0.80)
- **Grid-Search**: Optimales alpha über Backtesting findbar

**Warum das funktioniert:**
Der Markt aggregiert Millionen Euro Information. Ein reines Modell ignoriert das.
Die Kombination senkt die Varianz (weniger wilde Vorhersagen) und findet Edges
nur dort, wo das Modell wirklich anders denkt als der Markt.

```python
from shared.market_prior import MarketPrior

# Automatisch aus CLV kalibriert
prior = MarketPrior(clv_data=feedback_loop.get_clv_analysis(), sport='football')

# Modell + Markt kombinieren
posterior = prior.combine(
    model_probs={'1': 0.55, 'X': 0.25, '2': 0.20},
    market_odds={'1': 1.80, 'X': 3.50, '2': 4.50}
)
# → {'1': 0.533, 'X': 0.261, '2': 0.205}
```

---

## 📁 NEUE DATEIEN (v2.1)

```
shared/
├── backtesting.py        # Walk-Forward Backtest Framework
└── market_prior.py       # Bayesian Market Prior Integration

football/src/
├── data/
│   ├── __init__.py
│   └── xg_fetcher.py    # xG Datenquellen (Understat, football-data)
└── model/
    └── dixon_coles.py    # v2: xG-Training, Adaptive Decay, Promotion Handling
```

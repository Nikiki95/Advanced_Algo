# Betting Algorithm Infrastructure

## Überblick

Dieses Repository enthält ein automatisiertes Wettsystem für Football (9 Ligen), NBA (30 Teams) und NFL (32 Teams) mit Value-Bet Detection und Kelly-Staking.

---

## Modelle & Training

### ⚽ Football (Dixon-Coles Modell)

**9 Ligen:**
| Liga | Code | Teams | Spiele/Saison | Datenquelle |
|------|------|-------|---------------|-------------|
| Bundesliga | D1 | 18 | 306 | football-data.co.uk |
| 2. Bundesliga | D2 | 18 | 306 | football-data.co.uk |
| Premier League | E0 | 20 | 380 | football-data.co.uk |
| Championship | E1 | 24 | 552 | football-data.co.uk |
| La Liga | SP1 | 20 | 380 | football-data.co.uk |
| Serie A | I1 | 20 | 380 | football-data.co.uk |
| Ligue 1 | F1 | 18 | 306 | football-data.co.uk |
| Primeira Liga | P1 | 18 | 306 | football-data.co.uk |
| Eredivisie | N1 | 18 | 306 | football-data.co.uk |

**Modell-Parameter:**
- **Algorithmus:** Dixon-Coles (Poisson mit Abhängigkeitsparameter ρ)
- **ρ (Rho):** -0.13 (Negative Korrelation zwischen Heim- und Auswärts-Toren)
- **Decay:** 0.0035 (Gewichtung aktueller Spiele)
- **Training:** 3 Saisons (2023/24, 2024/25, 2025/26)
- **Datei:** `football/models/leagues/dixon_coles_{CODE}.pkl`

**Training:**
```bash
cd football
python train_all_leagues.py --all
```

---

### 🏀 NBA (ELO Modell mit Short Memory)

**30 Teams:**
- Alle NBA Teams (keine Duplikate mehr - LAC → LA Clippers gemerged)

**Modell-Parameter:**
- **Algorithmus:** ELO Rating System
- **K-Faktor:** 40 (erhöht für schnelle Anpassung)
- **Home Advantage:** 100 ELO-Punkte
- **Margin Multiplier:** 1.2
- **Short Memory:** Letzte 20 Spiele nur (~3-4 Wochen)
- **Initial ELO:** 1500

**Besonderheit:**
- **Short Memory Ansatz:** Nicht alle 2276 Spiele, sondern nur die letzten 20
- **Schnelle Anpassung:** Hoher K-Faktor (40 statt 20) für aktuelle Form
- **Saison-Regression:** 25% zwischen Saisons

**Training:**
```bash
cd nba
python retrain_model.py
```

**Output:**
- `nba/models/elo_model_2025_2026_{DATE}.pkl`
- Symlink: `elo_model_202603.pkl`

---

### 🏈 NFL (Power Ranking Modell)

**32 Teams:**
- Alle NFL Teams

**Modell-Parameter:**
- **Algorithmus:** Power Rankings + EPA (Expected Points Added)
- **Home Advantage:** 2.5 Punkte
- **Inter-Season Regression:** 30%
- **Learning Rate:** 30%
- **Spread StdDev:** 12.0 Punkte
- **Training Window:** 52 Wochen (letzte ~1 Saison)

**Besonderheit:**
- Kombiniert Power Rankings mit EPA-Daten
- Regression nur zwischen Saisons (nicht währenddessen)
- Spread-Cover Probability via Normalverteilung

**Training:**
```bash
cd nfl
python retrain_model.py
```

---

## Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                     DAILY CRON (07:30)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────┐
│  Football  │  │    NBA     │  │    NFL     │
│ 9 Ligen    │  │ 30 Teams   │  │ 32 Teams   │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │
      ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│              Value Engine (4% Threshold)                     │
│         Kelly Staking (25% Fraction, €1000 Bankroll)        │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │                       │
           ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Tracked Bets    │    │  Telegram Alerts │
│  (Shadow/Live)   │    │  (@Betconsultantbot)│
└──────────────────┘    └──────────────────┘
```

---

## Datenquellen

### TheOddsAPI (Free Tier - 500 Calls/Monat)
- **Football:** 9 Ligen ( soccer_germany_bundesliga, soccer_epl, etc.)
- **NBA:** basketball_nba
- **NFL:** americanfootball_nfl
- **Markets:** h2h, spreads, totals
- **Regions:** eu

### Football-Data.co.uk
- Historische Ergebnisse für Football
- CSV-Format, kostenlos
- 3 Saisons Backlog

### Fixturedownload.com
- NBA Spielpläne und Ergebnisse
- JSON-Format
- Saisons 2024/25 + 2025/26

---

## Konfiguration

### Secrets (`secrets/.env`)
```env
THEODDS_API_KEY=xxx                    # TheOddsAPI (500 calls/Monat)
TELEGRAM_BOT_TOKEN=xxx                 # @BotFather
TELEGRAM_CHAT_ID=-5192284960           # Algorithm Gruppe
EXECUTION_MODE=live                    # shadow oder live
PLAYER_PROPS_ENABLED=true              # Player Props aktiv
```

### Cron Jobs
```bash
# Daily Run (07:30)
30 7 * * * cd ~/.openclaw/workspace/betting-algorithm && \
  source .venv/bin/activate && \
  export $(grep -v '^#' secrets/.env | xargs) && \
  python -m shared.pipeline_runner daily

# 15-Min Check (On-Demand)
bash scripts/run_15min_check.sh
```

---

## Value Detection

### Threshold
- **Min Value:** 4% (0.04)
- **Kelly Fraction:** 25% (konservativ)
- **Max Stake:** €100 pro Bet (Bankroll-Schutz)

### Berechnung
```
Value = (FairOdds / MarketOdds) - 1
Kelly% = (p * (b - 1) - (1 - p)) / (b - 1)
Stake = Bankroll * KellyFraction * Kelly%
```

---

## Monitoring

### Logs
- `logs/cron_daily.log` - Tägliche Runs
- `logs/15min_*.log` - 15-Min Checks
- `data/tracked_bets/performance.json` - Performance-Tracking

### Commands
```bash
# Cron Status
crontab -l

# Letzte Bets
cat data/tracked_bets/performance.json

# Model Status
ls -la football/models/leagues/*.pkl
ls -la nba/models/*.pkl
ls -la nfl/models/*.pkl
```

---

## Bekannte Limitationen

1. **EuroLeague/Tennis:** Nicht im TheOddsAPI Free-Tier verfügbar
2. **Player Props:** Laufen mit Default-Priors (kein individuelles Training)
3. **Verletzungen:** Keine automatische Injury-Daten (API-SPORTS Key nötig)
4. **Roster Changes:** Short Memory (20 Spiele) hilft, aber keine echte Roster-Tracking

---

## GitHub

**Repository:** https://github.com/Nikiki95/Advanced_Algo

**Letzter Commit:**
```
d9f5369 Fix NBA team mapping: LAC -> LA Clippers to ensure exactly 30 teams
```

---

## Wartung

**Wöchentlich:**
- Performance-Check: `cat data/tracked_bets/performance.json`
- API-Quota: TheOddsAPI (500 calls/Monat)

**Monatlich:**
- Modelle neu trainieren (optional)
- Bankroll-Review
- Telegram Bot Test

**Bei Problemen:**
1. Logs prüfen: `tail -100 logs/cron_daily.log`
2. Modelle neu trainieren
3. API-Keys validieren

---

*Erstellt: 21.03.2026*
*Version: 7.3 mit Short Memory*

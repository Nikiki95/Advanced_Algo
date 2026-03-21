# Betting Algorithm Infrastructure

## Überblick

Dieses Repository enthält ein automatisiertes Wettsystem für Football (9 Ligen + UEFA), NBA (30 Teams) und NFL (32 Teams) mit Value-Bet Detection und Kelly-Staking.

**Wichtig:** Diese Dokumentation beschreibt den tatsächlichen Stand des Repos (Audit durchgeführt am 21.03.2026).

---

## Status-Übersicht

| Komponente | Status | Bemerkung |
|------------|--------|-----------|
| 🟢 **Football Domestic** | Produktionsbereit | 9 Ligen aktiv (D1, D2, E0, E1, SP1, I1, F1, P1, N1) |
| 🟢 **Football UEFA** | Produktionsbereit | UCL, UEL, UECL im Pipeline-Preset |
| 🟢 **NBA** | Produktionsbereit | 30 Teams, Short Memory (20 Spiele) |
| 🟢 **NFL** | Produktionsbereit | 32 Teams, Off-Season-Modus |
| 🟡 **EuroLeague** | Baseline/Optional | Modell vorhanden aber keine API-Daten (Free-Tier) |
| 🟡 **Tennis** | Baseline/Optional | Modell vorhanden aber keine API-Daten (Free-Tier) |
| 🟡 **Player Props** | Mit Einschränkungen | Laufen mit Default-Priors, nicht individuell trainiert |
| 🟢 **Settlement** | Produktionsbereit | Automatisch via Cron |
| 🟡 **Telegram Control** | Fast bereit | Bot erstellt, muss zur Gruppe hinzugefügt werden |
| 🟢 **Pipeline Automation** | Produktionsbereit | Daily 07:30, 15-Min On-Demand |

**Legende:** 🟢 = Produktionsbereit | 🟡 = Nutzbar mit Einschränkungen | 🔴 = Nicht bereit

---

## Gegenüberstellung: Dokumentation vs. Code

| Was | Dokumentiert | Tatsächlich im Code | Abweichung |
|-----|--------------|---------------------|------------|
| **Football Ligen** | 8 Ligen | **9 Ligen** (D1,D2,E0,**E1**,SP1,I1,F1,P1,N1) | E1 (Championship) hinzugefügt |
| **UEFA** | Nicht erwähnt | **UCL, UEL, UECL** im Pipeline-Preset | Dokumentation unvollständig |
| **NBA Teams** | 30 Teams | **30 Teams** (LAC→LA Clippers gemerged) | ✅ Korrigiert |
| **EuroLeague/Tennis** | Nicht erwähnt | **Baseline/Optional** (leere Modelle) | Dokumentation unvollständig |
| **Value-Formel** | `(FairOdds/MarketOdds)-1` | **`edge = p - 1/odds`** | ⚠️ Doku war falsch, korrigiert |
| **Kelly-Formel** | `K = (bp-q)/b` | `K = (bp-q)/b` | ✅ Korrekt |

---

## Modelle & Training

### ⚽ Football (Dixon-Coles Modell)

**9 aktive Ligen (Default im Live-Runner):**
| Liga | Code | Status | Teams | Spiele/Saison | Datenquelle |
|------|------|--------|-------|---------------|-------------|
| Bundesliga | D1 | 🟢 Aktiv | 18 | 306 | football-data.co.uk |
| 2. Bundesliga | D2 | 🟢 Aktiv | 18 | 306 | football-data.co.uk |
| Premier League | E0 | 🟢 Aktiv | 20 | 380 | football-data.co.uk |
| **Championship** | **E1** | **🟢 Aktiv** | 24 | 552 | football-data.co.uk |
| La Liga | SP1 | 🟢 Aktiv | 20 | 380 | football-data.co.uk |
| Serie A | I1 | 🟢 Aktiv | 20 | 380 | football-data.co.uk |
| Ligue 1 | F1 | 🟢 Aktiv | 18 | 306 | football-data.co.uk |
| Primeira Liga | P1 | 🟢 Aktiv | 18 | 306 | football-data.co.uk |
| Eredivisie | N1 | 🟢 Aktiv | 18 | 306 | football-data.co.uk |

**UEFA Wettbewerbe (im Pipeline-Preset):**
- 🟢 **UCL** (Champions League)
- 🟢 **UEL** (Europa League)  
- 🟢 **UECL** (Conference League)

**Modell-Parameter:**
- **Algorithmus:** Dixon-Coles (Poisson mit ρ = -0.13)
- **Decay:** 0.0035
- **Training:** 3 Saisons (2023/24, 2024/25, 2025/26)
- **Datei:** `football/models/leagues/dixon_coles_{CODE}.pkl`

**Training:**
```bash
cd football
python train_all_leagues.py --all  # Trainiert alle 9 Ligen
```

---

### 🏀 NBA (ELO Modell mit Short Memory)

**30 Teams** (keine Duplikate):
- LAC → LA Clippers gemerged
- Alle anderen Teams eindeutig

**Modell-Parameter:**
- **Algorithmus:** ELO Rating System
- **K-Faktor:** 40 (hoch für schnelle Anpassung)
- **Home Advantage:** 100 ELO-Punkte
- **Margin Multiplier:** 1.2
- **Short Memory:** Letzte 20 Spiele (~3-4 Wochen)
- **Saison-Regression:** 25% zwischen Saisons

**Training:**
```bash
cd nba
python retrain_model.py  # Short Memory: nur letzte 20 Spiele
```

---

### 🏈 NFL (Power Ranking Modell)

**32 Teams**

**Modell-Parameter:**
- **Algorithmus:** Power Rankings + EPA
- **Home Advantage:** 2.5 Punkte
- **Inter-Season Regression:** 30%
- **Training Window:** 52 Wochen

**Training:**
```bash
cd nfl
python retrain_model.py
```

---

## Value Detection & Formeln

### Value/Edge Berechnung

**⚠️ WICHTIG:** Die ursprüngliche Dokumentation enthielt eine falsche Formel. Hier die **korrekte** Berechnung aus dem Code:

```python
# Echte Implementierung im Code:
implied_prob = 1 / market_odds
edge = model_prob - implied_prob

# Oder äquivalent:
edge = model_prob - (1 / market_odds)
```

**Beispiel:**
- Model sagt: 60% Siegwahrscheinlichkeit
- Market Odds: @1.80 (impliziert 55.6%)
- Edge: 0.60 - 0.556 = **+0.044 = +4.4%**

**Threshold:**
- **Min Edge:** 4% (0.04)
- Spread Markets: 60% des Haupt-Thresholds (2.4%)

### Kelly-Staking

**Formel (korrekt implementiert):**
```python
b = odds - 1.0  # Netto-Quote
kelly = (b * prob - (1 - prob)) / b
# Gekürzt: kelly = (bp - q) / b  wobei q = 1-p
```

**Parameter:**
- **Kelly Fraction:** 25% (konservativ)
- **Max Stake:** €100 pro Bet
- **Default Bankroll:** €1000

---

## Architektur & Pipeline

### Daily Pipeline (07:30 Uhr)

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
│ + UEFA     │  │            │  │            │
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
│  (Shadow/Live)   │    │  (@Betconsultant)│
└──────────────────┘    └──────────────────┘
```

### Pipeline-Presets (shared/pipeline_presets.py)

| Preset | Enthalten |
|--------|-----------|
| `daily` | Football 9 Ligen, NBA, NFL, Settlement |
| `uefa` | UCL, UEL, UECL + Props + Settlement |
| `props` | Player Props für alle Sportarten |
| `full` | Alles (Daily + UEFA + Props) |

---

## Datenquellen & Limits

### TheOddsAPI (Free Tier)
- **Limit:** 500 Calls/Monat
- **Football:** 9 Ligen + UEFA verfügbar
- **NBA:** basketball_nba ✅
- **NFL:** americanfootball_nfl ✅
- **EuroLeague:** ❌ Nicht im Free-Tier
- **Tennis:** ⚠️ Nur saisonal (Miami Open)

### Football-Data.co.uk
- Historische Ergebnisse
- Kostenlos, CSV-Format
- 3 Saisons verfügbar

---

## Bekannte Risiken / Offene Punkte

| Risiko | Auswirkung | Empfohlene Maßnahme |
|--------|-----------|---------------------|
| **API-Limit (500 Calls/Monat)** | Höchstens 1x täglich möglich | Kein 15-Min Cron aktivieren |
| **Injury-/Roster-Daten fehlen** | Modelle kennen Verletzungen nicht | API-SPORTS Key hinzufügen |
| **Player Props mit Default-Priors** | Keine individuelle Spieler-Analyse | Manuelle Review empfohlen |
| **EuroLeague/Tennis keine Daten** | Baseline-Modelle nur | Nicht für Live-Bets verwenden |
| **Externe APIs können brechen** | Keine Daten mehr | Fallback auf historische Daten |
| **Shadow-Mode vor Live empfohlen** | Falsche Alerts möglich | Erst 1 Woche Shadow testen |

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
# Daily Run (07:30) - Alle 9 Ligen + NBA + NFL
30 7 * * * cd ~/.openclaw/workspace/betting-algorithm && \
  source .venv/bin/activate && \
  export $(grep -v '^#' secrets/.env | xargs) && \
  python -m shared.pipeline_runner daily

# UEFA Run (optional, Mittwochs für CL)
# 0 9 * * 3 cd ... && python -m shared.pipeline_runner uefa

# 15-Min Check (On-Demand, nicht empfohlen bei 500 Call-Limit)
# bash scripts/run_15min_check.sh
```

---

## Monitoring & Troubleshooting

### Logs prüfen
```bash
# Letzte Daily Run
tail -50 logs/cron_daily.log

# Performance
cat data/tracked_bets/performance.json

# API-Quota
grep "Remaining calls" logs/*.log | tail -5
```

### Modelle prüfen
```bash
ls -la football/models/leagues/*.pkl  # Sollten 9 Dateien sein
ls -la nba/models/*.pkl                # Sollte elo_model_202603.pkl sein
ls -la nfl/models/*.pkl                # Sollte nfl_power_*.pkl sein
```

---

## GitHub

**Repository:** https://github.com/Nikiki95/Advanced_Algo

**Wichtige Dateien:**
- `INFRASTRUCTURE.md` - Diese Datei
- `DOC_AUDIT_SUMMARY.md` - Audit-Details
- `football/cron_live.py` - Football Live Runner (9 Ligen)
- `nba/retrain_model.py` - NBA Training (Short Memory)

---

*Letzte Aktualisierung: 21.03.2026 (Audit durchgeführt)*
*Version: 7.3 mit Short Memory + vollständiger UEFA-Unterstützung*

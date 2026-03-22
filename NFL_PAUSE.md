# NFL Season Pause

**Status:** ⏸️ PAUSED  
**Grund:** Off-Season (keine Spiele)  
**Reaktivierung:** September 2026 (Start NFL Saison 2026/27)

---

## Warum pausiert?

1. **Keine Spiele** - NFL Saison endet Anfang Februar (Super Bowl)
2. **Off-Season Aktivitäten** - Free Agency, Draft, Training Camp verändern komplette Roster
3. **Power Rankings unbrauchbar** - Ohne aktuelle Spieldaten keine sinnvollen Rankings
4. **Verletzungen/Roster-Changes** - Zu viele Unbekannte im Off-Season

---

## Was ist deaktiviert?

| Komponente | Status | Grund |
|------------|--------|-------|
| `nfl/cron_live.py` | ⏸️ Pausiert | Keine aktuellen Spiele |
| `nfl/cron_props.py` | ⏸️ Pausiert | Keine aktuellen Spiele |
| `nfl/retrain_model.py` | ⏸️ Pausiert | Keine Trainingsdaten |
| NFL in `pipeline_presets.py` | ⏸️ Auskommentiert | Nicht im Daily/Props/Weekly |
| NFL Settlement | ⏸️ Pausiert | Keine offenen Wetten |

---

## Was bleibt erhalten?

- ✅ **NFL Modelle** - Bleiben gespeichert (`nfl/models/`)
- ✅ **Historische Daten** - Für zukünftiges Retraining
- ✅ **Code** - Alles intakt für Reaktivierung

---

## Reaktivierung im September 2026

### Schritte:
1. **Modelle neu trainieren** - Mit aktuellen 2026/27 Daten
2. **Cron-Jobs reaktivieren** - NFL wieder in `pipeline_presets.py` einkommentieren
3. **Power Rankings validieren** - Erste 2-3 Wochen beobachten
4. **Langsam hochfahren** - Erst Shadow Mode, dann Live

### Command für Reaktivierung:
```bash
# In pipeline_presets.py wieder einkommentieren:
# [PY, 'nfl/cron_live.py'],
# [PY, 'nfl/cron_props.py'],

# Dann neu trainieren:
cd nfl
python retrain_model.py
```

---

## Alternative im Off-Season (optional)

Falls trotzdem NFL-Aktivität gewünscht:
- **NFL Draft** (April) - Keine Value-Bets möglich
- **Preseason** (August) - Starters spielen nicht voll
- **Hockey/Baseball** - Andere Sportarten nutzen

**Empfehlung:** Fokus auf NBA + Football (Soccer) bis September.

---

*Pause begonnen: 21.03.2026*  
*Geplante Reaktivierung: September 2026*

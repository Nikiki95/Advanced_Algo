# Implemented Changes V7.3

## Telegram Admin Control erweitert

### Neue Befehle
- `/pipeline <name>` startet ein beliebiges Pipeline-Preset aus `shared.pipeline_presets`
- `/activate_model <sport> <version>` setzt ein registriertes Kandidatenmodell als aktives Modell

### Details
- `/pipeline` akzeptiert alle aktuell vorhandenen Presets (`daily`, `weekly`, `uefa`, `props`, `full`)
- optional kann `continue` bzw. `--continue-on-error` als Zusatzargument mitgegeben werden
- `/activate_model` protokolliert die Aktivierung mit Reason `telegram:<username>` in der Model Registry
- bei unbekannter Version werden die zuletzt verfügbaren Kandidaten für den Sport zurückgegeben

### Angepasste Dateien
- `shared/telegram_control_bot.py`
- `README.md`

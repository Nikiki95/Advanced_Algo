# 🕐 Cron-Job Setup für Automatische Checks

## Option 1: Host-Cron (empfohlen)

### 1. Crontab bearbeiten

```bash
crontab -e
```

### 2. Einträge hinzufügen

```bash
# Alle 30 Minuten prüfen (werktags 8-22 Uhr)
*/30 8-22 * * 1-5 cd /pfad/zu/betting-algorithm && ./venv/bin/python cron_runner.py >> logs/cron.log 2>&1

# Oder: Stündlich
0 8-22 * * 1-5 cd /pfad/zu/betting-algorithm && ./venv/bin/python cron_runner.py

# Oder: Morgens um 9 für Tages-Setup
0 9 * * * cd /pfad/zu/betting-algorithm && ./venv/bin/python cron_runner.py
```

### 3. Logs überwachen

```bash
# Cron Logs ansehen
tail -f logs/cron.log

# Letzte Checks
./venv/bin/python cron_runner.py --stats
```

---

## Option 2: Docker-Cron

### Starten

```bash
./run.sh cron-start
```

Oder manuell:

```bash
docker-compose --profile cron up -d
```

### Logs

```bash
docker-compose logs -f betting-cron
```

---

## 📋 Cron-Optionen

| Häufigkeit | Cron Expression | Nutzung |
|------------|---------------|---------|
| Stündlich | `0 * * * *` | Standard |
| Alle 30 Min | `*/30 * * * *` | Aktiv |
| Alle 2 Stunden | `0 */2 * * *` | Konservativ |
| Nur m
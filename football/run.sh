#!/bin/bash
# Sicheres Wrapper-Script für Docker-Ausführung

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}🎯 Value-Bet Algorithm Docker Runner${NC}"
echo "======================================"

# Prüfe Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker nicht installiert${NC}"
    exit 1
fi

# Prüfe .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env nicht gefunden - erstelle aus Template${NC}"
    cp .env.example .env
    echo -e "${YELLOW}📝 Bitte .env bearbeiten und Telegram-Token hinzufügen${NC}"
fi

# Funktionen
build() {
    echo -e "${GREEN}🔨 Baue Docker Image...${NC}"
    docker build -t betting-algo:latest .
}

run_once() {
    echo -e "${GREEN}▶️  Einmaliger Check...${NC}"
    docker run --rm \
        --name betting-algo-run \
        --read-only \
        -v "$(pwd)/data:/app/data" \
        -v "$(pwd)/models:/app/models" \
        -v "$(pwd)/.env:/app/.env:ro" \
        --memory="1g" \
        --cpus="1.0" \
        --network="bridge" \
        betting-algo:latest \
        python main.py --no-notify "$@"
}

run_with_notifications() {
    echo -e "${GREEN}🔔 Check mit Telegram-Benachrichtigungen...${NC}"
    docker run --rm \
        --name betting-algo-run \
        --read-only \
        -v "$(pwd)/data:/app/data" \
        -v "$(pwd)/models:/app/models" \
        -v "$(pwd)/.env:/app/.env:ro" \
        --memory="1g" \
        --cpus="1.0" \
        betting-algo:latest \
        python main.py "$@"
}

start_cron() {
    echo -e "${GREEN}🕐 Starte Cron-Service (alle 30 Min)...${NC}"
    docker-compose --profile cron up -d
    echo -e "${GREEN}✅ Cron läuft im Hintergrund${NC}"
    echo "Logs: docker-compose logs -f betting-cron"
}

stop_cron() {
    echo -e "${YELLOW}🛑 Stoppe Cron-Service...${NC}"
    docker-compose --profile cron down
}

shell() {
    echo -e "${GREEN}🐚 Interaktiver Shell-Zugriff...${NC}"
    docker run --rm -it \
        -v "$(pwd)/data:/app/data" \
        -v "$(pwd)/models:/app/models" \
        -v "$(pwd)/.env:/app/.env:ro" \
        --entrypoint /bin/bash \
        betting-algo:latest
}

clean() {
    echo -e "${YELLOW}🧹 Cleanup...${NC}"
    docker-compose down 2>/dev/null || true
    docker rm -f betting-algo-run 2>/dev/null || true
    docker rm -f betting-algo-cron 2>/dev/null || true
    echo -e "${GREEN}✅ Cleanup abgeschlossen${NC}"
}

logs() {
    docker-compose logs -f
}

# Haupt-Menu
case "${1:-help}" in
    build|b)
        build
        ;;
    run|r)
        run_once "${@:2}"
        ;;
    notify|n)
        run_with_notifications "${@:2}"
        ;;
    cron-start|cs)
        start_cron
        ;;
    cron-stop|cst)
        stop_cron
        ;;
    shell|sh)
        shell
        ;;
    logs|l)
        logs
        ;;
    clean)
        clean
        ;;
    help|h|--help|-h)
        echo ""
        echo "Usage: ./run.sh [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  build, b        Docker Image bauen"
        echo "  run, r          Einmaligen Check ausführen (ohne Notify)"
        echo "  notify, n       Check mit Telegram-Benachrichtigungen"
        echo "  cron-start, cs  Cron-Service starten (alle 30 Min)"
        echo "  cron-stop, cst  Cron-Service stoppen"
        echo "  shell, sh       Interaktiver Container-Zugriff"
        echo "  logs, l         Logs anzeigen"
        echo "  clean           Container aufräumen"
        echo ""
        ;;
    *)
        echo -e "${RED}❌ Unbekannter Befehl: $1${NC}"
        echo "Verwende: ./run.sh help"
        exit 1
        ;;
esac
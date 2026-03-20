#!/bin/bash
# Docker-Test Script - baut Image und macht Dry-Run

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 Docker Test & Build${NC}"
echo "======================"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker nicht installiert${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker verfügbar${NC}"

# Baue Image
echo -e "\n${BLUE}🔨 Baue Docker Image...${NC}"
docker build -t betting-algo:test .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Image erfolgreich gebaut${NC}"
else
    echo -e "${RED}❌ Build fehlgeschlagen${NC}"
    exit 1
fi

# Teste Python-Import im Container
echo -e "\n${BLUE}🧪 Teste Python-Imports...${NC}"
docker run --rm betting-algo:test python -c "
from src.model.dixon_coles import DixonColesModel
from src.scraper.sbr_scraper import MockSBRScraper
from src.engine.value_engine import ValueEngine
print('Alle Imports OK')
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Imports funktionieren${NC}"
else
    echo -e "${RED}❌ Import-Fehler${NC}"
    exit 1
fi

# Dry-Run mit Mock-Daten
echo -e "\n${BLUE}🏃 Dry-Run Test...${NC}"
docker run --rm \
    --read-only \
    -v "$(pwd)/data:/app/data" \
    -v "$(pwd)/models:/app/models" \
    betting-algo:test \
    python test.py

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}🎉 Docker Test erfolgreich!${NC}"
    echo ""
    echo -e "${BLUE}Nutzung:${NC}"
    echo "  ./run.sh build     # Produktions-Image bauen"
    echo "  ./run.sh run       # Einmaliger Check"
    echo "  ./run.sh cron-start # Automatisch alle 30 Min"
else
    echo -e "\n${RED}❌ Docker Test fehlgeschlagen${NC}"
    exit 1
fi
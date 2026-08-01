#!/usr/bin/env bash
set -euo pipefail

echo "=== Agente IA - Setup ==="

# Check prerequisites
for cmd in docker uv; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd no está instalado."
        exit 1
    fi
done

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo ">> .env creado desde .env.example — configura tus API keys."
fi

# Ensure REDIS_URL points to localhost (Docker exposes Redis on localhost:6379)
if grep -q "redis://redis:6379" .env 2>/dev/null; then
    sed -i 's|redis://redis:6379|redis://localhost:6379|g' .env
fi

# Install dependencies
echo ">> Instalando dependencias con uv..."
uv sync

# Start Redis via Docker if not already running
if docker ps --format '{{.Names}}' | grep -q "prototipo-agente-redis"; then
    echo ">> Redis ya está corriendo en Docker."
else
    echo ">> Levantando Redis en Docker..."
    docker compose up redis -d --wait
fi

# Start PostgreSQL via Docker if not already running
if docker ps --format '{{.Names}}' | grep -q "prototipo-agente-postgres"; then
    echo ">> PostgreSQL ya está corriendo en Docker."
else
    echo ">> Levantando PostgreSQL en Docker..."
    docker compose up postgres -d --wait
fi

# Apply database schema
echo ">> Aplicando schema de base de datos..."
uv run python scripts/init_db.py
echo "   Schema OK"

# Start FastAPI with uvicorn
echo ""
echo "=== Listo ==="
echo "  API:     http://localhost:8000"
echo "  Docs:    http://localhost:8000/docs"
echo "  Redis:   localhost:6379 (Docker)"
echo "  PG:      localhost:5434 (Docker)"
echo ""
echo "  Ctrl+C para detener. 'docker compose down' para apagar todo."
echo ""

exec uv run uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload

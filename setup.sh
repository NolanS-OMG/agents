#!/usr/bin/env bash
set -euo pipefail

cleanup() {
    echo ""
    echo ">> Deteniendo servicios..."
    docker compose down
    exit 0
}

trap cleanup INT TERM

echo "=== Agente IA - Setup ==="

# Check prerequisites
for cmd in docker uv; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd no está instalado."
        exit 1
    fi
done

# Limpiar puerto 8000 si está ocupado
echo ">> Limpiando puerto 8000..."
if lsof -ti:8000 &> /dev/null; then
    echo "   Matando procesos en puerto 8000..."
    kill -9 $(lsof -ti:8000) 2>/dev/null || true
fi

# Bajar contenedores Docker si están corriendo
echo ">> Bajando contenedores Docker existentes..."
docker compose down 2>/dev/null || true

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
if grep -q "^VOICE_ENABLED=true" .env 2>/dev/null; then
    uv sync --extra voice
else
    uv sync
fi

# Levantar Redis y PostgreSQL
echo ">> Levantando Redis y PostgreSQL en Docker..."
docker compose up redis postgres -d --wait

# Apply database migrations
echo ">> Aplicando migraciones de base de datos..."
if uv run aerich upgrade 2>/dev/null; then
    echo "   Migraciones aplicadas."
else
    echo "   DB nuevo detectado, inicializando schema..."
    uv run aerich init-db
    echo "   Schema inicial creado."
fi

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

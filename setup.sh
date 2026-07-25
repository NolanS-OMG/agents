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

# Install dependencies locally (for IDE support)
echo ">> Instalando dependencias con uv..."
uv sync

# Generate lock file if missing
if [ ! -f uv.lock ]; then
    uv lock
fi

# Build and start containers
echo ">> Levantando servicios con Docker Compose..."
docker compose up --build -d

echo ""
echo "=== Servicios levantados ==="
echo "  API:   http://localhost:8000"
echo "  Docs:  http://localhost:8000/docs (solo en modo DEBUG=true)"
echo "  Redis: localhost:6379"
echo ""
echo "Usa 'docker compose logs -f api' para ver los logs."
echo "Usa 'docker compose down' para detener los servicios."

#!/usr/bin/env bash
set -euo pipefail

echo "=== Agente IA - Setup ==="

# Check prerequisites
for cmd in docker uv redis-server; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "WARNING: $cmd no está instalado."
        if [ "$cmd" = "redis-server" ]; then
            echo "  Redis es opcional, el webhook funciona sin él (sin historial)."
        fi
    fi
done

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo ">> .env creado desde .env.example — configura tus API keys."
fi

# Check if .env has localhost Redis (for local dev)
if grep -q "redis://redis:6379" .env 2>/dev/null; then
    echo ">> Detectado REDIS_URL apuntando a Docker (redis://redis:6379)"
    echo "   Cambiando a localhost para dev local..."
    sed -i 's|redis://redis:6379|redis://localhost:6379|g' .env
fi

# Install dependencies locally (for IDE support)
echo ">> Instalando dependencias con uv..."
uv sync

# Generate lock file if missing
if [ ! -f uv.lock ]; then
    uv lock
fi

# Start Redis in background if available and not already running
if command -v redis-server &> /dev/null; then
    if ! pgrep -x redis-server > /dev/null; then
        echo ">> Iniciando Redis en background..."
        redis-server --daemonize yes --port 6379
    else
        echo ">> Redis ya está corriendo."
    fi
else
    echo ">> Redis no disponible, continuando sin historial de sesión."
fi

# Start FastAPI with uvicorn
echo ">> Iniciando FastAPI en http://0.0.0.0:8000..."
echo ""
echo "=== Servicios activos ==="
echo "  API:     http://localhost:8000"
echo "  Docs:    http://localhost:8000/docs (solo si DEBUG=true)"
if pgrep -x redis-server > /dev/null; then
    echo "  Redis:   localhost:6379 (activo)"
else
    echo "  Redis:   No disponible (historial deshabilitado)"
fi
echo ""
echo "NOTA: Para recibir webhooks de WhatsApp necesitas exponer el puerto 8000"
echo "      Corre 'ngrok http 8000' en otra terminal y configura la URL en Meta."
echo ""
echo "Presiona Ctrl+C para detener."
echo ""

exec uv run uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload

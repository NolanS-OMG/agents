#!/usr/bin/env bash
set -euo pipefail

# Deploy script for VPS
# Usage:
#   1. Clone repo on VPS
#   2. Create .env with production values
#   3. Run: ./deploy.sh

echo "=== Agente IA — Deploy ==="

# Check docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: docker not installed"
    exit 1
fi

# Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Create it with production values:"
    echo ""
    echo "  OPENROUTER_API_KEY=sk-or-v1-..."
    echo "  POSTGRES_PASSWORD=<strong_password>"
    echo "  CREDENTIAL_ENCRYPTION_KEY=<32_byte_hex>"
    echo "  VOICE_ENABLED=true"
    echo "  DEBUG=false"
    echo ""
    exit 1
fi

# Build and start
echo ">> Building and starting containers..."
docker compose up --build -d

# Wait for postgres
echo ">> Waiting for PostgreSQL..."
sleep 5

# Run migrations
echo ">> Running migrations..."
docker compose exec api python -m aerich upgrade 2>/dev/null || \
    docker compose exec api python -m aerich init-db 2>/dev/null || true

# Seed santa_lena data
echo ">> Seeding Santa Leña data..."
docker compose exec api python scripts/seed_santa_lena.py

echo ""
echo "=== Deploy complete ==="
echo "  API:    http://$(hostname -I | awk '{print $1}'):8000"
echo "  Health: http://$(hostname -I | awk '{print $1}'):8000/health"
echo ""
echo "  Twilio webhook (voice): https://<your-domain>/incoming-call/santa_lena"
echo "  Twilio webhook (WA):    https://<your-domain>/webhook/twilio-whatsapp/santa_lena"
echo ""
echo "  Logs: docker compose logs -f api"

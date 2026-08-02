#!/bin/bash
# Script para actualizar el prompt del tenant portfolio via API

API_KEY="sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm"
BASE_URL="http://localhost:8000"

echo "=== Actualizando prompt de portfolio ==="

# 1. Ver el prompt actual
echo -e "\n1. Prompt actual:"
curl -s "${BASE_URL}/api/v1/prompts/chat" \
  -H "X-API-Key: ${API_KEY}" | jq .

# 2. Actualizar con restricciones para respuestas más breves
echo -e "\n2. Actualizando prompt..."
curl -X PUT "${BASE_URL}/api/v1/prompts/chat" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "restricciones": "IMPORTANTE: Mantén las respuestas CONCISAS (máximo 150 palabras). Usa bullet points cuando sea apropiado. No expandas innecesariamente. Si el usuario pregunta por experiencia AI, resume en 3-4 puntos clave máximo."
  }' | jq .

echo -e "\n✅ Prompt actualizado. La cache de Redis se invalidó automáticamente."
echo "El siguiente mensaje al chat usará el nuevo prompt."

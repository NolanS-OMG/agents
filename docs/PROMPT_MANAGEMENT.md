# Prompt Management API

**Última actualización:** 2026-08-02  
**Base URL:** http://localhost:8000

---

## 🎯 ¿Qué son los Prompts?

Los prompts controlan cómo responde el asistente de IA:
- **Tono:** Profesional, casual, técnico, etc.
- **Formato:** Markdown, bullet points, párrafos
- **Restricciones:** Longitud máxima, reglas específicas
- **Ejemplos:** Ejemplos de respuestas ideales

Cada tenant puede tener múltiples prompts con diferentes "estilos".

---

## 📋 Endpoints Disponibles

### 1. Listar todos los prompts

```bash
GET /api/v1/prompts
```

**Ejemplo:**
```bash
curl http://localhost:8000/api/v1/prompts \
  -H "X-API-Key: sk_portfoli_..."
```

**Response:**
```json
[
  {
    "estilo": "informativo",
    "system_prompt": "Eres el asistente virtual...",
    "tono": "profesional y cercano",
    "formato": "markdown",
    "vocabulario": "[]",
    "ejemplos": "[]",
    "restricciones": "[\"Máximo 150 palabras\"]",
    "active": true
  }
]
```

---

### 2. Obtener un prompt específico

```bash
GET /api/v1/prompts/{estilo}
```

**Ejemplo:**
```bash
curl http://localhost:8000/api/v1/prompts/informativo \
  -H "X-API-Key: sk_portfoli_..."
```

---

### 3. Crear un nuevo prompt

```bash
POST /api/v1/prompts
```

**Body:**
```json
{
  "estilo": "casual",
  "system_prompt": "Eres un asistente amigable y relajado...",
  "tono": "casual y cercano",
  "formato": "texto simple",
  "vocabulario": "[\"genial\", \"cool\", \"súper\"]",
  "ejemplos": "[]",
  "restricciones": "[\"No usar tecnicismos\"]"
}
```

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/api/v1/prompts \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "estilo": "casual",
    "system_prompt": "Eres un asistente amigable...",
    "tono": "casual"
  }'
```

---

### 4. Actualizar un prompt existente

```bash
PUT /api/v1/prompts/{estilo}
```

**Body (todos los campos son opcionales):**
```json
{
  "system_prompt": "Nuevo texto del prompt...",
  "tono": "más formal",
  "restricciones": "[\"Máximo 100 palabras\", \"Usa emojis\"]"
}
```

**Ejemplo - Hacer respuestas más concisas:**
```bash
curl -X PUT http://localhost:8000/api/v1/prompts/informativo \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "restricciones": "[\"Máximo 150 palabras por respuesta\", \"Usa bullet points\", \"Prioriza información clave\"]"
  }'
```

**Ejemplo - Cambiar el tono:**
```bash
curl -X PUT http://localhost:8000/api/v1/prompts/informativo \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "tono": "muy técnico y formal"
  }'
```

---

### 5. Eliminar un prompt (soft delete)

```bash
DELETE /api/v1/prompts/{estilo}
```

**Ejemplo:**
```bash
curl -X DELETE http://localhost:8000/api/v1/prompts/casual \
  -H "X-API-Key: sk_portfoli_..."
```

**Response:** 204 No Content

---

## 🔧 Campos del Prompt

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `estilo` | string | ✅ Sí (crear) | Identificador único del prompt (ej: "informativo", "casual", "técnico") |
| `system_prompt` | string | ✅ Sí (crear) | Instrucciones principales para el LLM |
| `tono` | string | ❌ No | Descripción del tono deseado |
| `formato` | string | ❌ No | Formato de salida preferido |
| `vocabulario` | string | ❌ No | JSON array de palabras/frases a usar |
| `ejemplos` | string | ❌ No | JSON array de ejemplos de respuestas |
| `restricciones` | string | ❌ No | JSON array de reglas/restricciones |

---

## 💡 Casos de Uso Comunes

### 1. Hacer respuestas más breves

```bash
curl -X PUT http://localhost:8000/api/v1/prompts/informativo \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "restricciones": "[\"Máximo 150 palabras\", \"Sé conciso\", \"Bullet points cuando sea apropiado\"]"
  }'
```

### 2. Cambiar a un tono más técnico

```bash
curl -X PUT http://localhost:8000/api/v1/prompts/informativo \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "tono": "muy técnico, usa jerga de programación",
    "vocabulario": "[\"arquitectura\", \"pipelines\", \"orquestación\", \"microservicios\"]"
  }'
```

### 3. Agregar emojis a las respuestas

```bash
curl -X PUT http://localhost:8000/api/v1/prompts/informativo \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "restricciones": "[\"Usa emojis relevantes al inicio de cada sección\", \"Mantén tono amigable\"]"
  }'
```

### 4. Forzar respuestas en inglés

```bash
curl -X PUT http://localhost:8000/api/v1/prompts/informativo \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "restricciones": "[\"SIEMPRE responde en inglés, incluso si el usuario escribe en español\"]"
  }'
```

---

## 🚀 Script Automatizado

Puedes usar el script incluido para actualizar el prompt de portfolio:

```bash
./scripts/update_portfolio_prompt.sh
```

O crear tu propio script personalizado:

```bash
#!/bin/bash
API_KEY="sk_portfoli_..."
BASE_URL="http://localhost:8000"

# Actualizar restricciones
curl -X PUT "${BASE_URL}/api/v1/prompts/informativo" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "restricciones": "[\"Máximo 100 palabras\", \"Usa emojis\"]"
  }'

echo "✅ Prompt actualizado"
```

---

## ⚡ Caché y Propagación

**IMPORTANTE:** Cuando actualizas un prompt:

1. ✅ El backend **invalida automáticamente** el caché de Redis
2. ✅ El **siguiente mensaje** al chat usará el nuevo prompt inmediatamente
3. ❌ Las conversaciones **en curso** pueden terminar con el prompt anterior

**No necesitas reiniciar el servidor** - los cambios son inmediatos.

---

## 🧪 Testing

Después de actualizar el prompt, prueba con un mensaje simple:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: sk_portfoli_..." \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about Nolan'\''s AI experience",
    "language": "en"
  }'
```

Verifica que la respuesta refleje las nuevas restricciones (longitud, tono, formato).

---

## 📊 Ejemplo JavaScript/TypeScript

```typescript
const API_KEY = 'sk_portfoli_...';
const BASE_URL = 'http://localhost:8000';

async function updatePromptBrevity(estilo: string) {
  const response = await fetch(`${BASE_URL}/api/v1/prompts/${estilo}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({
      restricciones: JSON.stringify([
        'Máximo 150 palabras',
        'Usa bullet points',
        'Sé conciso'
      ])
    })
  });

  if (!response.ok) {
    throw new Error('Failed to update prompt');
  }

  return await response.json();
}

// Uso
await updatePromptBrevity('informativo');
console.log('✅ Prompt actualizado');
```

---

## ❓ FAQ

### ¿Cómo sé qué estilo usa mi tenant?

El estilo se configura en el archivo `.env`:
```bash
ESTILO=informativo
```

Por defecto es `"chat"`, pero portfolio usa `"informativo"`.

### ¿Puedo tener múltiples prompts activos?

Sí, pero solo se usa el que coincide con `ESTILO` en el `.env`.

### ¿Los cambios afectan conversaciones en curso?

Las conversaciones activas pueden terminar con el prompt anterior. Los nuevos mensajes usan el prompt actualizado.

### ¿Cómo revierto un cambio?

Usa `PUT` con los valores anteriores, o recrea el prompt desde un backup.

---

## 📞 Soporte

**GitHub:** https://github.com/NolanS-OMG/prototipo-agente  
**Email:** nolan1scott3@gmail.com

---

**Última actualización:** 2026-08-02 02:20 UTC

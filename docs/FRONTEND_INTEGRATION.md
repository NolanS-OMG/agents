# API Integration Guide for Frontend

**Fecha:** 2026-08-01  
**Versión:** MVP (Sin tools)  
**Estado:** ✅ Implementado y probado

---

## 🔑 API Key

**Clave actual para portfolio:**
```
sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm
```

⚠️ **Guardar en variable de entorno, NO commitear al repositorio**

**Regenerar si es necesario:**
```bash
uv run python scripts/list_api_keys.py --tenant portfolio --generate
```

---

## 🌐 Base URL

- **Desarrollo:** `http://localhost:8000`
- **Producción:** TBD

---

## ✅ Endpoints Disponibles

### 1. Health Check
```http
GET /api/v1/health

Response 200:
{
  "status": "healthy",
  "timestamp": "2026-08-01T23:58:39.908563+00:00",
  "version": "1.0.0"
}
```

**Uso:** Llamar cada 30-60s cuando chat esté abierto para verificar disponibilidad.

---

### 2. Welcome Message
```http
GET /api/v1/chat/welcome
Headers:
  X-API-Key: sk_portfoli_...

Response 200:
{
  "message": "👋 Hi! I'm Nolan's AI assistant...",
  "suggestions": [
    "Tell me about his AI experience",
    "What projects has he built?",
    "Show me his tech stack",
    "How can I contact him?"
  ]
}
```

**Uso:** Mostrar al abrir el chat por primera vez (sin gastar tokens del LLM).

---

### 3. Send Message
```http
POST /api/v1/chat
Headers:
  X-API-Key: sk_portfoli_...
  Content-Type: application/json

Body:
{
  "message": "What projects has Nolan built?",
  "session_id": "abc123",  // opcional, se genera automáticamente
  "language": "en"         // "en" o "es", default: "en"
}

Response 200:
{
  "session_id": "7e00c968-6ad7-482f-8916-4662ed2f0ec4",
  "response": "Here's a summary...",
  "tool_used": null  // Siempre null en MVP
}
```

**Notas:**
- Si no envías `session_id`, el backend genera uno y lo setea en cookie
- El frontend puede reutilizar el `session_id` de la respuesta
- `language` controla el idioma de la respuesta del LLM

---

### 4. Get Session History
```http
GET /api/v1/chat/session/{session_id}/history
Headers:
  X-API-Key: sk_portfoli_...

Response 200:
{
  "session_id": "7e00c968-6ad7-482f-8916-4662ed2f0ec4",
  "messages": [
    {
      "role": "user",
      "content": "What is Nolan's experience?"
    },
    {
      "role": "assistant",
      "content": "Here's a summary..."
    }
  ]
}
```

**Uso:** Precargar historial cuando usuario vuelve al chat (e.g., después de reload).

---

### 5. Delete Session
```http
DELETE /api/v1/chat/session/{session_id}
Headers:
  X-API-Key: sk_portfoli_...

Response: 204 No Content
```

**Uso:** Limpiar sesión (testing, reset, "clear chat").

---

## 🚫 MVP - SIN TOOLS

**Importante:** El MVP NO incluye tool calling para controlar el frontend.

El chat solo responde preguntas sobre:
- Experiencia profesional de Nolan
- Proyectos destacados
- Stack tecnológico
- Educación y certificaciones
- Información de contacto

**Tools se implementarán en Fase 2:**
- `scrollToSection` - Scroll automático a secciones
- `openLink` - Abrir enlaces externos
- `downloadCV` - Descargar currículum
- etc.

---

## 🔒 Rate Limiting

**Límites actuales (DESARROLLO - muy altos):**
- **1000 mensajes/hora** por sesión
- **100 mensajes/minuto** por sesión

**Response cuando se excede:**
```http
HTTP 429 Too Many Requests
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please wait a moment.",
  "retry_after_seconds": 30
}
```

⚠️ **Ajustar a límites reales en producción** (ej: 20/hora, 5/minuto)

---

## ⚠️ Error Handling

### HTTP Status Codes
- `200` - OK
- `204` - No Content (delete successful)
- `400` - Bad Request (mensaje inválido, parámetros incorrectos)
- `401` - Unauthorized (API key inválida o faltante)
- `429` - Too Many Requests (rate limit excedido)
- `500` - Internal Server Error
- `503` - Service Unavailable (LLM provider temporalmente caído)

### Error Format
```json
{
  "error": "error_code",
  "message": "Human-readable message"
}
```

**Códigos de error:**
- `missing_api_key` - No se envió X-API-Key header
- `invalid_api_key` - API key incorrecta o inactiva
- `rate_limit_exceeded` - Límite de requests excedido
- `service_unavailable` - Servicio temporalmente no disponible

---

## 🌐 CORS

**Orígenes permitidos:**
- `http://localhost:5173` (Vite dev)
- `http://localhost:3000` (Alt dev)
- `https://nolanashcraft.netlify.app` (Producción)

**Headers permitidos:**
- `Content-Type`
- `X-API-Key`

**Credentials:** Habilitado (cookies para session_id)

---

## 💻 Ejemplo de Uso (JavaScript/TypeScript)

```typescript
const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm';

// 1. Verificar health
async function checkHealth() {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`);
  const data = await res.json();
  return data.status === 'healthy';
}

// 2. Obtener welcome message
async function getWelcome() {
  const res = await fetch(`${API_BASE_URL}/api/v1/chat/welcome`, {
    headers: { 'X-API-Key': API_KEY }
  });
  return await res.json();
}

// 3. Enviar mensaje
async function sendMessage(message: string, sessionId?: string, language = 'en') {
  const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY
    },
    credentials: 'include', // Importante para cookies
    body: JSON.stringify({
      message,
      session_id: sessionId,
      language
    })
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.message || 'Chat request failed');
  }

  return await res.json();
}

// 4. Obtener historial
async function getHistory(sessionId: string) {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/chat/session/${sessionId}/history`,
    { headers: { 'X-API-Key': API_KEY } }
  );
  return await res.json();
}

// 5. Limpiar sesión
async function clearSession(sessionId: string) {
  await fetch(
    `${API_BASE_URL}/api/v1/chat/session/${sessionId}`,
    {
      method: 'DELETE',
      headers: { 'X-API-Key': API_KEY }
    }
  );
}

// Ejemplo de flujo completo
async function initChat() {
  // 1. Verificar que el servicio está disponible
  const isHealthy = await checkHealth();
  if (!isHealthy) {
    console.error('Service is unhealthy');
    return;
  }

  // 2. Mostrar welcome message
  const welcome = await getWelcome();
  console.log(welcome.message);
  console.log('Suggestions:', welcome.suggestions);

  // 3. Enviar primer mensaje (sin session_id, se genera automático)
  const response1 = await sendMessage('Tell me about Nolan', undefined, 'en');
  console.log('Session ID:', response1.session_id);
  console.log('Response:', response1.response);

  // 4. Continuar conversación con el mismo session_id
  const response2 = await sendMessage(
    'What projects has he built?',
    response1.session_id,
    'en'
  );
  console.log('Response:', response2.response);

  // 5. Obtener historial completo
  const history = await getHistory(response1.session_id);
  console.log('Messages:', history.messages);
}
```

---

## 🧪 Testing desde curl

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Welcome
curl http://localhost:8000/api/v1/chat/welcome \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm"

# Chat (inglés)
curl http://localhost:8000/api/v1/chat \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is Nolan'\''s experience?","language":"en"}'

# Chat (español)
curl http://localhost:8000/api/v1/chat \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm" \
  -H "Content-Type: application/json" \
  -d '{"message":"Cuál es la experiencia de Nolan?","language":"es"}'

# History (reemplazar session_id)
curl http://localhost:8000/api/v1/chat/session/{session_id}/history \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm"

# Delete session
curl -X DELETE http://localhost:8000/api/v1/chat/session/{session_id} \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm"
```

---

## 📋 Session Management

**El backend maneja sesiones automáticamente:**
1. Frontend envía request sin `session_id`
2. Backend genera UUID y lo setea en cookie `session_id`
3. Requests siguientes pueden:
   - Usar la cookie automáticamente (enviando `credentials: 'include'`)
   - O enviar el `session_id` en el body

**TTL:**
- Redis: 1 hora (cache)
- PostgreSQL: Permanente (histórico)

**Recomendación:** Guardar el `session_id` en localStorage para recuperar conversaciones después de reload.

---

## 📞 Contacto Backend

- **GitHub:** https://github.com/NolanS-OMG/prototipo-agente
- **Email:** nolan1scott3@gmail.com

---

## 🔄 Próximos Pasos (Fase 2)

1. **Tools para frontend:**
   - `scrollToSection` - Scroll automático
   - `openLink` - Abrir enlaces
   - `downloadCV` - Descargar currículum

2. **Analytics:**
   - Feedback endpoint (thumbs up/down)
   - Métricas de engagement
   - Preguntas más frecuentes

3. **Mejoras:**
   - SSE streaming para respuestas largas
   - `/health/detailed` con métricas de componentes
   - Rate limiting ajustado a producción

---

**Última actualización:** 2026-08-01 23:59 UTC

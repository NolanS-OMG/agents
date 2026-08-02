# API Request Specifications - Frontend Integration

**Última actualización:** 2026-08-02  
**Backend:** http://localhost:8000

---

## ⚠️ IMPORTANTE: Headers Requeridos

**Todos los requests (excepto `/health`)** DEBEN incluir:

```http
X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm
Content-Type: application/json
```

---

## 📋 Endpoint: POST /api/v1/chat

### Request Body Schema

```typescript
{
  "message": string,        // REQUERIDO - min 1 char, max 4096 chars
  "session_id"?: string,    // OPCIONAL - omitir o null, NO enviar string vacío ""
  "channel"?: string,       // OPCIONAL - default: "api"
  "language"?: string       // OPCIONAL - "en" o "es", default: "en"
}
```

### ✅ Ejemplos CORRECTOS

#### Primer mensaje (sin session_id):
```json
{
  "message": "Tell me about Nolan's experience"
}
```

#### Primer mensaje con idioma español:
```json
{
  "message": "Cuéntame sobre la experiencia de Nolan",
  "language": "es"
}
```

#### Mensaje en conversación existente:
```json
{
  "message": "What projects has he built?",
  "session_id": "7e00c968-6ad7-482f-8916-4662ed2f0ec4",
  "language": "en"
}
```

#### Con session_id null (también válido):
```json
{
  "message": "Hello",
  "session_id": null
}
```

### ❌ Ejemplos INCORRECTOS

#### NO enviar session_id como string vacío:
```json
{
  "message": "Hello",
  "session_id": ""  // ❌ ESTO CAUSA ERROR 422
}
```

#### NO enviar message vacío:
```json
{
  "message": ""  // ❌ ESTO CAUSA ERROR 422
}
```

#### NO usar language inválido:
```json
{
  "message": "Hello",
  "language": "fr"  // ❌ Solo "en" o "es" son válidos
}
```

#### NO enviar session_id con caracteres inválidos:
```json
{
  "message": "Hello",
  "session_id": "abc 123"  // ❌ Solo letras, números, guiones y guiones bajos
}
```

---

## 📋 Validaciones del Backend

### Campo `message`:
- **Tipo:** `string`
- **Requerido:** Sí
- **Min length:** 1 carácter
- **Max length:** 4096 caracteres

### Campo `session_id`:
- **Tipo:** `string | null`
- **Requerido:** No
- **Default:** `null` (el backend genera uno automáticamente)
- **Min length:** 1 carácter (si se envía)
- **Max length:** 128 caracteres
- **Pattern:** `^[a-zA-Z0-9_\-]+$` (solo alfanuméricos, guiones y guiones bajos)
- **⚠️ IMPORTANTE:** Si no tienes session_id, **OMITE EL CAMPO** o envía `null`. NO envíes `""`

### Campo `language`:
- **Tipo:** `string`
- **Requerido:** No
- **Default:** `"en"`
- **Valores válidos:** `"en"` o `"es"`
- **Pattern:** `^(en|es)$`

### Campo `channel`:
- **Tipo:** `string`
- **Requerido:** No
- **Default:** `"api"`

---

## 🔄 Manejo del session_id

### Primera interacción:
1. Frontend **NO envía** `session_id` (o envía `null`)
2. Backend genera UUID y lo retorna en response
3. Frontend **guarda** el `session_id` de la response

### Interacciones subsecuentes:
1. Frontend **envía** el `session_id` guardado
2. Backend mantiene el contexto de la conversación
3. Response incluye el mismo `session_id`

### Limpiar conversación:
1. Frontend llama `DELETE /api/v1/chat/session/{session_id}`
2. Genera nuevo `session_id` con el siguiente request (omitiendo el campo)

---

## 📤 Response Format

### Success (200 OK):
```json
{
  "session_id": "7e00c968-6ad7-482f-8916-4662ed2f0ec4",
  "response": "Nolan is a software engineer...",
  "tool_used": null
}
```

### Error 422 (Validation Error):
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "message"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {"min_length": 1}
    }
  ]
}
```

### Error 401 (Unauthorized):
```json
{
  "error": "invalid_api_key",
  "message": "Invalid API key"
}
```

### Error 429 (Rate Limit):
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please wait a moment.",
  "retry_after_seconds": 30
}
```

---

## 🧪 Testing con cURL

### Request mínimo válido:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'
```

### Request completo:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about Nolan",
    "language": "en"
  }'
```

### Request con session_id:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What projects has he built?",
    "session_id": "7e00c968-6ad7-482f-8916-4662ed2f0ec4",
    "language": "en"
  }'
```

---

## 💻 Ejemplo JavaScript/TypeScript

```typescript
const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm';

interface ChatRequest {
  message: string;
  session_id?: string | null;  // Opcional, omitir o null
  language?: 'en' | 'es';
  channel?: string;
}

interface ChatResponse {
  session_id: string;
  response: string;
  tool_used: string | null;
}

async function sendMessage(
  message: string,
  sessionId?: string | null,
  language: 'en' | 'es' = 'en'
): Promise<ChatResponse> {
  // Construir payload - IMPORTANTE: solo incluir session_id si existe
  const payload: ChatRequest = { message, language };
  
  if (sessionId) {
    payload.session_id = sessionId;
  }
  // Si sessionId es null o undefined, NO incluir el campo

  const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    credentials: 'include', // Para cookies
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    console.error('Chat error:', error);
    throw new Error(error.message || 'Chat request failed');
  }

  return await response.json();
}

// Uso:
// Primera vez (sin session_id)
const result1 = await sendMessage('Tell me about Nolan', null, 'en');
console.log('Session ID:', result1.session_id);

// Siguiente mensaje (con session_id)
const result2 = await sendMessage(
  'What projects has he built?',
  result1.session_id,
  'en'
);
```

---

## 🔍 Debugging

### Si recibes error 422:

1. **Verifica el payload exacto que envías:**
   ```javascript
   console.log('Sending:', JSON.stringify(payload, null, 2));
   ```

2. **Revisa que `message` no esté vacío:**
   ```javascript
   if (!message || message.trim().length === 0) {
     throw new Error('Message cannot be empty');
   }
   ```

3. **Si no tienes session_id, NO lo incluyas:**
   ```javascript
   // ✅ CORRECTO
   const payload = { message, language };
   
   // ❌ INCORRECTO
   const payload = { message, session_id: '', language };
   ```

4. **Verifica que language sea 'en' o 'es':**
   ```javascript
   const validLanguages = ['en', 'es'];
   if (!validLanguages.includes(language)) {
     throw new Error('Invalid language');
   }
   ```

### Si recibes error 401:

1. Verifica que el header `X-API-Key` esté presente
2. Verifica que la API key sea exactamente: `sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm`
3. No agregues espacios antes/después de la key

### Si recibes error 429:

1. Espera el tiempo indicado en `retry_after_seconds`
2. Reduce la frecuencia de requests
3. Los límites actuales son: 1000/hora, 100/minuto por sesión

---

## 📞 Soporte

**GitHub:** https://github.com/NolanS-OMG/prototipo-agente  
**Email:** nolan1scott3@gmail.com

---

**Última actualización:** 2026-08-02 02:10 UTC

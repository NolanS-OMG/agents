# Frontend Integration Guide

## Resumen

El backend ahora **genera automáticamente** el `session_id` y lo retorna en el response + cookie. El frontend solo necesita:

1. Hacer requests a `/api/v1/chat` con `credentials: 'include'`
2. (Opcional) Guardar el `session_id` del response en localStorage como backup
3. (Opcional) Enviar metadata adicional para analytics

---

## Setup Básico (React 18/19)

### 1. Configurar Variables de Entorno

```bash
# .env.local o .env
VITE_API_URL=https://tu-backend.com
VITE_API_KEY=portfolio_xxxxx
```

### 2. Hook de Chat (Simple)

```typescript
// src/hooks/useChat.ts
import { useState } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatResponse {
  session_id: string;
  response: string;
  tool_used: string | null;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(text: string): Promise<void> {
    setIsLoading(true);
    setError(null);

    // Agregar mensaje del usuario a la UI inmediatamente
    const userMessage: Message = { role: 'user', content: text };
    setMessages(prev => [...prev, userMessage]);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': import.meta.env.VITE_API_KEY,
        },
        credentials: 'include',  // ← IMPORTANTE: envía/recibe cookies
        body: JSON.stringify({
          message: text,
          // session_id se omite, backend lo genera automáticamente
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: ChatResponse = await response.json();

      // Agregar respuesta del asistente
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response,
      };
      setMessages(prev => [...prev, assistantMessage]);

      // Opcional: guardar session_id en localStorage como backup
      if (data.session_id) {
        localStorage.setItem('portfolio_session_id', data.session_id);
      }

    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Error desconocido';
      setError(errorMsg);
      console.error('Error sending message:', err);
    } finally {
      setIsLoading(false);
    }
  }

  return { messages, sendMessage, isLoading, error };
}
```

### 3. Componente de Chat

```tsx
// src/components/Chat.tsx
import { useState } from 'react';
import { useChat } from '../hooks/useChat';

export function Chat() {
  const [input, setInput] = useState('');
  const { messages, sendMessage, isLoading, error } = useChat();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    await sendMessage(input);
    setInput('');
  };

  return (
    <div className="chat-container">
      {/* Mensajes */}
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <strong>{msg.role === 'user' ? 'Tú' : 'Nolan'}:</strong>
            <p>{msg.content}</p>
          </div>
        ))}
        {isLoading && <div className="loading">Escribiendo...</div>}
        {error && <div className="error">{error}</div>}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregúntame sobre mi experiencia..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !input.trim()}>
          Enviar
        </button>
      </form>
    </div>
  );
}
```

---

## Setup con Metadata (Fase 2)

Para enviar datos adicionales de analytics:

```typescript
// src/hooks/useChat.ts (versión con metadata)

function getClientMetadata() {
  return {
    screen_resolution: `${window.screen.width}x${window.screen.height}`,
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    pixel_ratio: window.devicePixelRatio,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
  };
}

export function useChat() {
  // ... (mismo código de arriba)

  async function sendMessage(text: string): Promise<void> {
    // ...

    const body = {
      message: text,
      metadata: getClientMetadata(),  // ← Metadata opcional
    };

    const response = await fetch(url, {
      // ...
      body: JSON.stringify(body),
    });

    // ...
  }
}
```

**Backend necesita actualizar ChatMessage model:**

```python
# src/app/api/routes/chat.py
class ChatMessage(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=4096)
    channel: str = Field(default="api")
    metadata: dict[str, Any] | None = None  # ← Agregar esto
```

---

## CORS Configuration

Si tu backend y frontend están en dominios diferentes:

### Backend (FastAPI)

```python
# src/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev
        "https://nolanashcraft.netlify.app",  # Producción
    ],
    allow_credentials=True,  # ← IMPORTANTE para cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Frontend (Vite/CRA)

**Desarrollo local con proxy (opcional):**

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

Entonces en el código:

```typescript
fetch('/api/v1/chat', {  // Proxy automático a localhost:8000
  // ...
});
```

---

## UTM Parameters & Campaign Tracking

```typescript
// src/utils/analytics.ts

export function getCampaignData() {
  const urlParams = new URLSearchParams(window.location.search);
  
  const data = {
    utm_source: urlParams.get('utm_source'),
    utm_medium: urlParams.get('utm_medium'),
    utm_campaign: urlParams.get('utm_campaign'),
    utm_content: urlParams.get('utm_content'),
    utm_term: urlParams.get('utm_term'),
  };

  // Guardar en localStorage para persistir en la sesión
  if (Object.values(data).some(v => v !== null)) {
    localStorage.setItem('campaign_data', JSON.stringify(data));
  }

  // Retornar data guardada si no hay UTM en URL actual
  const stored = localStorage.getItem('campaign_data');
  return stored ? JSON.parse(stored) : data;
}
```

**Enviar en metadata:**

```typescript
const metadata = {
  ...getClientMetadata(),
  ...getCampaignData(),
};
```

---

## Session Recovery (Si Borran Cookies)

Si el usuario borra cookies pero tienes el `session_id` en localStorage:

```typescript
// src/hooks/useChat.ts

async function sendMessage(text: string): Promise<void> {
  // ...

  // Intentar recuperar session_id de localStorage como fallback
  const savedSessionId = localStorage.getItem('portfolio_session_id');

  const body = {
    message: text,
    session_id: savedSessionId || undefined,  // ← Enviar explícitamente
  };

  const response = await fetch(url, {
    // ...
    body: JSON.stringify(body),
  });

  // ...
}
```

**Backend prioriza:** cookie > body.session_id > genera nuevo

---

## Testing Local

### 1. Probar que cookies funcionan

```typescript
// En DevTools Console
document.cookie  // Debe mostrar "session_id=..."
```

### 2. Verificar CORS

```typescript
// Si ves este error:
// "No 'Access-Control-Allow-Origin' header"

// Solución: agregar tu dominio frontend a allow_origins en backend
```

### 3. Probar persistencia de sesión

```typescript
// 1. Enviar mensaje
// 2. Recargar página (F5)
// 3. Enviar otro mensaje
// 4. Debe recordar contexto (misma sesión)
```

---

## Deployment Checklist

### Backend

- [ ] Variables de entorno configuradas (API keys, DATABASE_URL)
- [ ] CORS configurado con dominio de producción
- [ ] Cookies `secure=true` en producción (HTTPS)
- [ ] PostgreSQL accesible desde backend

### Frontend

- [ ] `VITE_API_URL` apunta a backend de producción
- [ ] `VITE_API_KEY` configurada (no commitear en git)
- [ ] `credentials: 'include'` en todos los fetch
- [ ] Build optimizado (`npm run build`)

### DNS/SSL

- [ ] Backend tiene HTTPS (requerido para cookies httpOnly + secure)
- [ ] Frontend tiene HTTPS (Netlify lo hace automático)
- [ ] Dominios en CORS allowlist

---

## Common Issues

### 1. Cookies no se guardan

**Causa:** Backend sin HTTPS pero cookie con `secure=true`

**Fix:** En desarrollo, backend usa `secure=false` (automático con `request.url.scheme`)

### 2. CORS error

**Causa:** Frontend domain no está en `allow_origins`

**Fix:** Agregar dominio exacto a lista (no usar `*` con `allow_credentials=True`)

### 3. Session no persiste entre reloads

**Causa:** Cookie no se está enviando

**Fix:** Verificar `credentials: 'include'` en fetch

### 4. 401 Unauthorized

**Causa:** API key incorrecta o faltante

**Fix:** Verificar header `X-API-Key` en request

---

## Ejemplo Completo Mínimo

```typescript
// src/App.tsx
import { useState } from 'react';

function App() {
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([]);
  const [input, setInput] = useState('');

  const send = async () => {
    if (!input.trim()) return;

    setMessages(prev => [...prev, { role: 'user', content: input }]);

    const res = await fetch('http://localhost:8000/api/v1/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'portfolio_xxxxx',
      },
      credentials: 'include',
      body: JSON.stringify({ message: input }),
    });

    const data = await res.json();
    setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    setInput('');
  };

  return (
    <div>
      <div>
        {messages.map((m, i) => (
          <div key={i}><strong>{m.role}:</strong> {m.content}</div>
        ))}
      </div>
      <input value={input} onChange={e => setInput(e.target.value)} />
      <button onClick={send}>Send</button>
    </div>
  );
}

export default App;
```

---

## Recursos

- [MDN: Using Fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)
- [MDN: HTTP Cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [Vite Env Variables](https://vitejs.dev/guide/env-and-mode.html)

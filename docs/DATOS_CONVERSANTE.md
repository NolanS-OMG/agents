# Datos del Conversante - Diseño y Estrategia

## Datos Actualmente Recopilados

### Nivel Sesión (ChatSession)
```python
- session_id: UUID generado por backend
- ip_address: IP del cliente (considera proxies)
- user_agent: String completo del navegador
- referrer: De dónde vino (Google, LinkedIn, etc.)
- language: Accept-Language header
- created_at / last_active: Timestamps
```

## Datos Adicionales a Recopilar (Futuro)

### 1. Geolocalización (IP → Location)
**Cómo:** Usar API gratuita como `ipapi.co` o `ip-api.com`

```python
# Ejemplo
async def enrich_ip_data(ip: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://ipapi.co/{ip}/json/")
        data = resp.json()
        return {
            "country": data.get("country_code"),  # "MX"
            "region": data.get("region"),         # "Nuevo León"
            "city": data.get("city"),             # "Monterrey"
            "timezone": data.get("timezone"),     # "America/Monterrey"
        }
```

**Por qué:**
- ✅ Ver de dónde vienen tus visitantes (México, USA, Europa)
- ✅ Ajustar horarios de respuesta (timezone)
- ✅ Personalizar contenido (español vs inglés)
- ✅ Detectar patrones: "muchos de California → mi perfil atrae SV startups"

**Costo:** Gratis hasta 1000 requests/día (ipapi.co), suficiente para portfolio

---

### 2. Parsing de User-Agent
**Cómo:** Librería `user-agents` o `httpagentparser`

```python
from user_agents import parse

ua_string = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
ua = parse(ua_string)

device_data = {
    "device_type": "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop",
    "browser": ua.browser.family,        # "Chrome", "Safari", "Firefox"
    "browser_version": ua.browser.version_string,
    "os": ua.os.family,                  # "Windows", "macOS", "Android", "iOS"
    "os_version": ua.os.version_string,
    "is_bot": ua.is_bot,                 # True si es crawler
}
```

**Por qué:**
- ✅ Filtrar bots (no contaminar analytics con crawlers)
- ✅ Optimizar experiencia: "70% mobile → priorizar diseño responsive"
- ✅ Debug: "Safari iOS tiene bug en el chat → específico de navegador"

**Costo:** Gratis (librería local)

---

### 3. Client Hints (Navegadores Modernos)
**Cómo:** Headers `Sec-CH-UA-*` enviados automáticamente por Chrome/Edge

```python
client_hints = {
    "platform": request.headers.get("sec-ch-ua-platform"),          # "Windows", "macOS"
    "mobile": request.headers.get("sec-ch-ua-mobile"),              # "?0" (desktop), "?1" (mobile)
    "platform_version": request.headers.get("sec-ch-ua-platform-version"),
    "brands": request.headers.get("sec-ch-ua"),                     # Brands del browser
}
```

**Por qué:**
- ✅ Más preciso que User-Agent (no falseable fácilmente)
- ✅ Deprecation-proof (User-Agent strings se están reduciendo)

**Limitaciones:** Solo Chrome/Edge modernos, Firefox/Safari no lo soportan aún

---

### 4. Screen Resolution & Viewport
**Cómo:** Enviado desde frontend

```typescript
// En tu chat component
const screenData = {
  screen_resolution: `${window.screen.width}x${window.screen.height}`,
  viewport: `${window.innerWidth}x${window.innerHeight}`,
  pixel_ratio: window.devicePixelRatio,  // Retina displays
  color_depth: window.screen.colorDepth,
};

fetch('/api/v1/chat', {
  body: JSON.stringify({
    message: "...",
    metadata: screenData  // ← Nuevo campo opcional
  })
});
```

**Backend:**
```python
class ChatMessage(BaseModel):
    session_id: str | None = None
    message: str
    metadata: dict | None = None  # ← Recibir aquí
```

**Por qué:**
- ✅ Detectar "muchos en 1920x1080 → diseño desktop-first es OK"
- ✅ Debug: "usuarios con viewport < 375px tienen layout roto"
- ✅ Retina displays (devicePixelRatio > 1) → optimizar assets

---

### 5. Tiempo de Interacción
**Cómo:** Timestamps en frontend

```typescript
// Inicio de sesión
const sessionStart = Date.now();

// Al enviar mensaje
const messageTimestamp = Date.now();
const timeSinceStart = messageTimestamp - sessionStart;

fetch('/api/v1/chat', {
  body: JSON.stringify({
    message: "...",
    metadata: {
      time_on_page_ms: timeSinceStart,  // Cuánto estuvo antes de preguntar
    }
  })
});
```

**Por qué:**
- ✅ Engagement: "usuarios que envían primer mensaje < 10s → muy interesados"
- ✅ Bounce detection: "95% se van sin preguntar → mejorar CTA"
- ✅ Patterns: "mensajes después de 5min → leyeron todo el portfolio primero"

---

### 6. UTM Parameters & Campaign Tracking
**Cómo:** Parse URL query params

```python
# En frontend, leer de URL
const urlParams = new URLSearchParams(window.location.search);
const campaignData = {
  utm_source: urlParams.get('utm_source'),      // "linkedin", "github"
  utm_medium: urlParams.get('utm_medium'),      // "social", "email"
  utm_campaign: urlParams.get('utm_campaign'),  // "hiring-q1-2026"
};

// Guardar en localStorage y enviar en primer mensaje
```

**Por qué:**
- ✅ Attribution: "50% vienen de LinkedIn → invertir más ahí"
- ✅ Campaigns: "email blast trajo 20 conversaciones → ROI positivo"
- ✅ A/B testing: "utm_campaign=variant-a vs variant-b"

---

### 7. Referrer Analysis
**Ya lo tienes:** `request.headers.get("referer")`

**Cómo mejorar:** Parse el dominio

```python
from urllib.parse import urlparse

referrer = request.headers.get("referer", "")
domain = urlparse(referrer).netloc if referrer else "direct"

referrer_category = {
    "linkedin.com": "social",
    "github.com": "dev_community",
    "google.com": "search",
    "": "direct",  # Tráfico directo (URL en barra)
}[domain]
```

**Por qué:**
- ✅ Funnel analysis: "LinkedIn → proyecto AI → contacto"
- ✅ SEO: "Google trae tráfico pero no convierte → mejorar keywords"

---

### 8. Session Duration & Message Patterns
**Cómo:** Calcular en analytics

```sql
-- Query PostgreSQL
SELECT 
  session_id,
  EXTRACT(EPOCH FROM (last_active - created_at)) / 60 as duration_minutes,
  COUNT(messages) as total_messages,
  COUNT(messages) / NULLIF(EXTRACT(EPOCH FROM (last_active - created_at)) / 60, 0) as messages_per_minute
FROM chat_sessions
WHERE tenant_id = 'portfolio'
GROUP BY session_id;
```

**Por qué:**
- ✅ Engagement: "sesiones largas (>10min) → usuarios muy interesados"
- ✅ Patterns: "1 mensaje/sesión → usuarios hacen 1 pregunta y se van"
- ✅ Conversion: "sesiones con 5+ mensajes → alta probabilidad de contacto"

---

### 9. Intent Classification (Futuro con ML)
**Cómo:** Clasificar el primer mensaje del usuario

```python
# Ejemplo con embeddings o keyword matching
def classify_intent(message: str) -> str:
    keywords = {
        "hiring": ["contratar", "job", "hiring", "work", "oportunidad"],
        "collaboration": ["colaborar", "proyecto", "together", "partnership"],
        "learning": ["cómo", "tutorial", "aprender", "how"],
        "feedback": ["opino", "feedback", "suggestion"],
    }
    
    for intent, words in keywords.items():
        if any(w in message.lower() for w in words):
            return intent
    return "general"
```

**Almacenar:**
```python
class ChatSession(Model):
    ...
    intent: CharField(max_length=50, null=True)  # "hiring", "collaboration", etc.
```

**Por qué:**
- ✅ Priorización: "80% intent=hiring → enfocar portfolio en eso"
- ✅ Personalization: Si intent=learning → responder con más detalles técnicos
- ✅ Conversion funnel: "hiring intent → 60% termina en contacto"

---

### 10. Technology Fingerprint (Avanzado)
**Cómo:** Librería `FingerprintJS` (frontend)

```typescript
import FingerprintJS from '@fingerprintjs/fingerprintjs';

const fp = await FingerprintJS.load();
const result = await fp.get();

const fingerprint = {
  visitor_id: result.visitorId,  // Hash único del browser
  confidence: result.confidence, // 0-1, qué tan confiable es
};
```

**Por qué:**
- ✅ Track usuarios entre sesiones (incluso si borran cookies/localStorage)
- ✅ Anti-fraud: detectar bots sofisticados
- ✅ Analytics: "usuario X volvió 3 veces en 2 semanas → muy interesado"

**Privacidad:** Controversial, usar solo si tienes privacy policy clara

---

## Priorización: Qué Implementar Primero

### Fase 1: Low-Hanging Fruit (ya tienes backend listo)
1. ✅ **Geolocalización** (ipapi.co)
2. ✅ **User-Agent parsing** (user-agents lib)
3. ✅ **Client Hints** (headers ya están, solo parsear)

**Esfuerzo:** 1-2 horas  
**Valor:** Alto (insights de dónde/cómo te encuentran)

---

### Fase 2: Frontend Metadata
4. **Screen resolution & viewport** (JS simple)
5. **Time on page** (Date.now())
6. **UTM parameters** (URLSearchParams)

**Esfuerzo:** 2-3 horas  
**Valor:** Medio-alto (engagement + attribution)

---

### Fase 3: Analytics y Dashboards
7. **Session duration queries** (SQL)
8. **Referrer categorization** (parsing)
9. **Intent classification** (keywords básicos)

**Esfuerzo:** 3-4 horas  
**Valor:** Alto (convertir datos en insights accionables)

---

### Fase 4: Advanced (solo si escala)
10. **FingerprintJS** (solo si necesitas cross-session tracking)

**Esfuerzo:** 4+ horas  
**Valor:** Bajo (overkill para portfolio, útil para SaaS)

---

## Privacidad y GDPR

### Datos que SÍ puedes recopilar sin consentimiento (Legitimate Interest):
- ✅ IP address (for analytics, not sold)
- ✅ User-Agent (technical necessity)
- ✅ Referrer (attribution)
- ✅ Session behavior (aggregate analytics)

### Datos que REQUIEREN consentimiento explícito:
- ❌ Fingerprinting cross-site
- ❌ Vender datos a terceros
- ❌ Tracking fuera de tu dominio

### Recomendación:
1. Agregar banner simple: "Usamos cookies para analytics (no vendemos datos)"
2. Link a Privacy Policy básica (template gratis: termsfeed.com)
3. No implementar FingerprintJS sin banner de consentimiento

---

## Dashboard Ejemplo (Futuro)

```
📊 Portfolio Analytics

Total Sessions: 247
└─ Last 7 days: 42
└─ Unique IPs: 198

Top Countries:
🇲🇽 Mexico: 45%
🇺🇸 USA: 30%
🇨🇦 Canada: 15%

Top Referrers:
1. linkedin.com: 40%
2. github.com: 25%
3. Direct: 20%
4. google.com: 15%

Devices:
💻 Desktop: 65%
📱 Mobile: 30%
📱 Tablet: 5%

Avg Session Duration: 3.2 min
Avg Messages/Session: 2.4

Intent Breakdown:
🎯 Hiring: 60%
🤝 Collaboration: 25%
📚 Learning: 10%
💬 General: 5%
```

---

## Siguiente Paso Recomendado

Implementar **Fase 1** (geolocalización + user-agent parsing) ahora que el backend está listo.

¿Quieres que lo haga?

# Tareas Críticas para Integración Frontend

## 🔴 CRÍTICO - Debe estar antes de MVP

### 1. CORS Middleware
**Estado:** ❌ No existe  
**Prioridad:** BLOQUEANTE  
**Descripción:** Sin CORS, el frontend no puede hacer requests desde localhost ni Netlify.

**Implementación:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000", 
        "https://nolanashcraft.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)
```

**Archivo:** `src/app/main.py`

---

### 2. Health Check Endpoint
**Estado:** ✅ Ya existe `/api/v1/health`  
**Acción:** Verificar que retorna el formato esperado:
```json
{
  "status": "healthy",
  "timestamp": "2026-08-01T12:00:00Z",
  "version": "1.0.0"
}
```

**Archivo:** `src/app/api/routes/health.py`

---

### 3. Parámetro `language` en Chat
**Estado:** ❌ No existe  
**Prioridad:** ALTA  
**Descripción:** Permitir al frontend especificar idioma (EN/ES) para que el LLM responda en ese idioma.

**Cambios en API:**
```python
class ChatMessage(BaseModel):
    session_id: str | None = ...
    message: str = ...
    channel: str = Field(default="api")
    language: str = Field(default="en", pattern="^(en|es)$")  # NUEVO
```

**Inyección en system prompt:**
```python
# En agent_router.py o chat.py
if language == "es":
    self._system_prompt += "\n\nIMPORTANTE: Responde SIEMPRE en español."
else:
    self._system_prompt += "\n\nIMPORTANT: Always respond in English."
```

**Archivos afectados:**
- `src/app/api/routes/chat.py`
- `src/app/services/agent_router.py` (opcional, si se inyecta ahí)

---

### 4. Session History Endpoint
**Estado:** ❌ No existe  
**Prioridad:** ALTA  
**Descripción:** Permitir al frontend obtener historial de una sesión sin enviar mensaje nuevo.

**Implementación:**
```python
@router.get("/chat/session/{session_id}/history")
async def get_session_history(
    request: Request,
    tenant_ctx: CurrentTenant,
    session_id: str = Path(..., min_length=1, max_length=128),
) -> dict:
    redis = request.app.state.redis
    if not redis:
        return {"messages": []}
    
    session = SessionManager(redis, tenant_id=tenant_ctx.tenant_id)
    history = await session.get_history(session_id)
    
    # Filtrar solo user y assistant messages con content
    messages = [
        {"role": m.role, "content": m.content, "timestamp": "..."}
        for m in history
        if m.role in ("user", "assistant") and m.content
    ]
    
    return {
        "session_id": session_id,
        "messages": messages
    }
```

**Archivo:** `src/app/api/routes/chat.py`

---

### 5. Delete Session Endpoint
**Estado:** ❌ No existe  
**Prioridad:** MEDIA  
**Descripción:** Permitir limpiar una sesión completamente (útil para testing).

**Implementación:**
```python
@router.delete("/chat/session/{session_id}")
async def delete_session(
    request: Request,
    tenant_ctx: CurrentTenant,
    session_id: str = Path(..., min_length=1, max_length=128),
) -> Response:
    redis = request.app.state.redis
    if redis:
        # Limpiar Redis
        await redis.delete(
            f"session:{session_id}:history",
            f"session:{session_id}:summary",
            f"session:{session_id}:needs_human",
        )
    
    # Opcional: limpiar PostgreSQL también
    # from src.app.db.models import ChatSession
    # session = await ChatSession.get_or_none(session_id=session_id, tenant_id=tenant_ctx.tenant_id)
    # if session:
    #     await session.delete()
    
    return Response(status_code=204)
```

**Archivo:** `src/app/api/routes/chat.py`

---

### 6. Welcome Message Endpoint
**Estado:** ❌ No existe  
**Prioridad:** MEDIA  
**Descripción:** Retornar mensaje inicial + sugerencias sin llamar al LLM.

**Implementación:**
```python
@router.get("/chat/welcome")
async def get_welcome_message(
    tenant_ctx: CurrentTenant,
) -> dict:
    # Hardcodeado por tenant
    if tenant_ctx.tenant_id == "portfolio":
        return {
            "message": "👋 Hi! I'm Nolan's AI assistant. I can help you learn about his experience with AI systems, projects, tech stack, and more. What would you like to know?",
            "suggestions": [
                "Tell me about his AI experience",
                "What projects has he built?",
                "Show me his tech stack",
                "How can I contact him?"
            ]
        }
    
    # Default genérico
    return {
        "message": "👋 Hello! How can I help you today?",
        "suggestions": []
    }
```

**Archivo:** `src/app/api/routes/chat.py`

---

### 7. Rate Limiting por Sesión
**Estado:** ❌ No existe (solo hay middleware de guardrails)  
**Prioridad:** MEDIA  
**Descripción:** Implementar límites absurdos para desarrollo, ajustar después.

**Límites propuestos (DESARROLLO):**
- 1000 mensajes por sesión por hora
- 100 mensajes por minuto

**Implementación:**
```python
async def check_rate_limit(redis, session_id: str) -> tuple[bool, int]:
    """Returns (is_allowed, retry_after_seconds)"""
    
    # Key: rate:session:{id}:hour
    hour_key = f"rate:session:{session_id}:hour"
    hour_count = await redis.incr(hour_key)
    
    if hour_count == 1:
        await redis.expire(hour_key, 3600)  # 1 hora
    
    if hour_count > 1000:
        ttl = await redis.ttl(hour_key)
        return False, ttl
    
    # Key: rate:session:{id}:minute
    min_key = f"rate:session:{session_id}:minute"
    min_count = await redis.incr(min_key)
    
    if min_count == 1:
        await redis.expire(min_key, 60)  # 1 minuto
    
    if min_count > 100:
        ttl = await redis.ttl(min_key)
        return False, ttl
    
    return True, 0
```

**Uso en chat endpoint:**
```python
allowed, retry_after = await check_rate_limit(redis, session_id)
if not allowed:
    raise HTTPException(
        status_code=429,
        detail={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please wait a moment.",
            "retry_after_seconds": retry_after
        }
    )
```

**Archivos:**
- `src/app/middleware/rate_limit.py` (nuevo)
- `src/app/api/routes/chat.py` (integrar check)

---

### 8. Error Responses Estandarizados
**Estado:** ⚠️ Revisar actual  
**Prioridad:** MEDIA  
**Descripción:** Asegurar que errores usen HTTP status codes + JSON body consistente.

**Formato esperado:**
```json
{
  "error": "error_code",
  "message": "Human-readable message"
}
```

**Verificar que se usen:**
- 400 - Bad Request (mensaje inválido, parámetros faltantes)
- 401 - Unauthorized (API key inválida)
- 429 - Too Many Requests (rate limit)
- 500 - Internal Server Error (error inesperado)
- 503 - Service Unavailable (LLM provider caído)

**Archivos afectados:**
- `src/app/api/routes/chat.py`
- `src/app/middleware/auth.py`

---

## 🟢 OPCIONAL - Mejoras Fase 2

### 9. Health Check Detallado
**Endpoint:** `GET /api/v1/health/detailed`  
**Descripción:** Incluir status de Redis, PostgreSQL, LLM provider, métricas.

---

### 10. Analytics/Feedback
**Endpoints:** 
- `POST /api/v1/chat/feedback`
- Métricas de engagement

**Descripción:** Dejarlo para cuando haya tráfico real.

---

## 📋 Checklist de Verificación Pre-Deploy

- [ ] CORS configurado con dominios correctos
- [ ] `/api/v1/health` retorna formato esperado
- [ ] Chat acepta parámetro `language` (en/es)
- [ ] `GET /chat/session/{session_id}/history` funciona
- [ ] `DELETE /chat/session/{session_id}` funciona
- [ ] `/chat/welcome` retorna mensaje hardcodeado
- [ ] Rate limiting implementado (aunque sea con límites altos)
- [ ] Errores retornan HTTP status codes correctos
- [ ] Test desde frontend en localhost:5173
- [ ] Test desde frontend en Netlify

---

## 🚀 Orden de Implementación Sugerido

1. **CORS** (5 min) - Bloqueante
2. **Health check verification** (5 min) - Ya existe, solo verificar
3. **Language parameter** (20 min) - Impacto en UX
4. **Session history GET** (30 min) - Importante para UX
5. **Welcome message** (15 min) - Mejora onboarding
6. **Delete session** (15 min) - Útil para testing
7. **Rate limiting** (45 min) - Protección básica
8. **Error standardization** (30 min) - Consistencia

**Total estimado:** ~3 horas

---

**Última actualización:** 2026-08-01

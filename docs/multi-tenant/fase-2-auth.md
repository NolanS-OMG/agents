# Fase 2: Autenticación + Tenant Resolution

## Objetivo

Que cualquier request con API key válida resuelva automáticamente su tenant, inyecte el contexto, y aplique rate limiting per-tenant.

---

## 2.1 Credential Vault Service

**Archivo nuevo:** `src/app/services/credential_vault.py`

- `encrypt(plaintext) -> ciphertext`
- `decrypt(ciphertext) -> plaintext`
- Usa Fernet con key de `settings.credential_encryption_key`
- Si no hay key configurada, raise error en startup

---

## 2.2 API Key Generation

**Formato:** `sk_{tenant_prefix}_{32_chars_random}`
**Storage:** SHA-256 del key completo en `api_keys.key_hash`
**Prefix:** se guarda para identificar sin exponer el key (`sk_santa_`)

```python
import secrets, hashlib

def generate_api_key(tenant_id: str) -> tuple[str, str]:
    """Returns (raw_key, key_hash)."""
    prefix = f"sk_{tenant_id[:8]}_"
    random_part = secrets.token_urlsafe(24)
    raw_key = prefix + random_part
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash
```

---

## 2.3 Auth Middleware

**Archivo nuevo:** `src/app/middleware/auth.py`

```python
# Flujo:
# 1. Extraer X-API-Key del header
# 2. SHA-256 hash
# 3. SELECT api_keys WHERE key_hash = ? AND active = true
# 4. Si no existe → 401
# 5. Cargar tenant → request.state.tenant_context
# 6. Update last_used_at (async, no bloquea)
```

Rutas excluidas del auth:
- `GET /health`
- `POST /webhook/whatsapp/{tenant_id}` (usa verify_token de Meta)
- `POST /incoming-call/{tenant_id}` (autenticado por Twilio signature)
- `GET /docs`

---

## 2.4 TenantContext Dataclass

**Archivo nuevo:** `src/app/services/tenant_context.py`

```python
@dataclass
class TenantContext:
    tenant_id: str
    tenant_name: str
    config: dict  # overrides
    scopes: list[str]  # del API key
```

---

## 2.5 FastAPI Dependency

**Archivo nuevo:** `src/app/api/deps.py`

```python
async def get_current_tenant(request: Request) -> TenantContext:
    ctx = getattr(request.state, "tenant_context", None)
    if not ctx:
        raise HTTPException(401, "API key required")
    return ctx
```

Uso en routes:
```python
@router.post("/converse")
async def converse(tenant: Annotated[TenantContext, Depends(get_current_tenant)]):
    ...
```

---

## 2.6 Rate Limiting Per-Tenant

Modificar `src/app/middleware/rate_limit.py`:
- Key actual: `ratelimit:{sender_id}`
- Key nuevo: `ratelimit:{tenant_id}:{conversant_id}`
- Límites default: 100 req/min per tenant, 20 req/min per conversant
- Overridable en `tenant.config` JSON

---

## 2.7 Tests

- Auth con key válida → 200 + TenantContext correcto
- Auth con key inválida → 401
- Auth con key inactiva → 401
- Auth sin header → 401
- Rate limit per-tenant funciona
- Rutas excluidas no requieren auth

---

## Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `src/app/services/credential_vault.py` | **NUEVO** |
| `src/app/middleware/auth.py` | **NUEVO** |
| `src/app/services/tenant_context.py` | **NUEVO** |
| `src/app/api/deps.py` | **NUEVO** |
| `src/app/middleware/rate_limit.py` | Modificar (namespace) |
| `src/app/main.py` | Registrar auth middleware |
| `tests/test_auth.py` | **NUEVO** |

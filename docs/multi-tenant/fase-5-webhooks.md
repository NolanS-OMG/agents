# Fase 5: Webhooks Multi-Tenant

## Objetivo

Cada tenant tiene su propio webhook de WhatsApp y número de Twilio, con credentials cargadas de DB.

---

## 5.1 WhatsApp Webhook Parametrizado

**Archivo:** `src/app/api/routes/webhook.py` (refactorizar)

Cambiar:
```
POST /webhook/whatsapp          → POST /webhook/whatsapp/{tenant_id}
GET  /webhook/whatsapp          → GET  /webhook/whatsapp/{tenant_id}
```

El tenant_id en el path permite que cada cliente configure su webhook en Meta apuntando a:
```
https://api.tuagente.com/webhook/whatsapp/santa_lena
```

### Flujo:
1. Extraer `tenant_id` del path
2. Cargar `TenantCredentials` de DB
3. Verificar `hub_verify_token` contra el del tenant (no global)
4. Construir `WhatsAppAdapter` con las credentials del tenant
5. El resto del flujo es igual (dedup, rate limit, agent, send)

---

## 5.2 Twilio Voice Parametrizado

**Archivo:** `src/app/api/routes/voice.py` (refactorizar)

Cambiar:
```
POST /incoming-call             → POST /incoming-call/{tenant_id}
WS   /ws/media-stream           → WS   /ws/media-stream/{tenant_id}
```

Cada número de Twilio se configura en el panel apuntando a:
```
https://api.tuagente.com/incoming-call/santa_lena
```

---

## 5.3 Credentials de DB

Actualmente las credentials vienen de `settings` (variables de entorno globales). Cambiar a:

```python
async def get_tenant_credentials(tenant_id: str) -> TenantCredentials:
    creds = await TenantCredentials.get_or_none(tenant_id=tenant_id)
    if not creds:
        raise HTTPException(404, "Tenant not configured")
    return creds

# Decrypt al usar:
whatsapp_token = vault.decrypt(creds.whatsapp_access_token_enc)
```

---

## 5.4 Meta Webhook Signature Validation

Meta envía `X-Hub-Signature-256` en cada webhook. Validar con el app secret del tenant:

```python
import hmac, hashlib

def verify_meta_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    expected = "sha256=" + hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## 5.5 Tests

- Webhook WhatsApp con tenant_id válido → procesa
- Webhook con tenant_id inexistente → 404
- Verify token correcto del tenant → responde challenge
- Verify token incorrecto → 403
- Llamada Twilio a tenant_id → TwiML correcto con stream URL del tenant

---

## Archivos a modificar

| Archivo | Acción |
|---------|--------|
| `src/app/api/routes/webhook.py` | Parametrizar con {tenant_id} |
| `src/app/api/routes/voice.py` | Parametrizar con {tenant_id} |
| `src/app/main.py` | Actualizar route registration |
| `tests/test_webhook_multitenant.py` | **NUEVO** |

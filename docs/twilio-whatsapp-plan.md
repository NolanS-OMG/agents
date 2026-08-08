# WhatsApp via Twilio — Setup + Implementación

## Lo que TÚ tienes que hacer (paso a paso)

### Opción A: Sandbox (demos inmediatas, hoy mismo)

1. Entra a [Twilio Console](https://console.twilio.com) → Messaging → Try it out → Send a WhatsApp message
2. Acepta los términos de WhatsApp
3. Te aparecerá un código tipo `join hungry-fox`
4. Los clientes que quieras demo tienen que mandar ese mensaje a **+1 (415) 523-8886** por WhatsApp
5. En la config del Sandbox, pon tu webhook URL: `https://tu-ngrok.ngrok.io/webhook/twilio-whatsapp/{tenant_id}`
6. Listo — ya pueden hablar con el agente

**Limitaciones del Sandbox:**
- Cada persona tiene que hacer el "join" antes de poder hablar
- La sesión expira en 3 días (deben re-join)
- No puedes usar tu número (+52 33 2101 6770), usan el de Twilio
- Solo para demos/desarrollo

### Opción B: Producción (tu número +52 33 2101 6770)

**Requisitos previos:**
1. Cuenta Twilio con billing configurado (no trial)
2. Un **Meta Business Portfolio** (antes "Facebook Business Manager") donde tú seas admin
3. Tu número de Twilio NO debe estar registrado en WhatsApp personal/Business (✓ ya que lo compraste en Twilio)

**Pasos:**
1. Twilio Console → Messaging → Senders → WhatsApp Senders
2. Click "Create new sender"
3. Selecciona tu número +52 33 2101 6770
4. Te pedirá autenticarte con Facebook (popup OAuth) — autoriza a Twilio
5. Crea un nuevo Meta Business Portfolio (o selecciona uno existente) y un WhatsApp Business Account (WABA)
6. Configura el perfil del negocio: nombre ("Tu Agente IA"), categoría, descripción
7. Verifica el número con OTP (Twilio te lo muestra en la consola ya que es número Twilio)
8. Confirma los accesos de Twilio

**Después de aprobación (1-5 días hábiles):**
- Configura el webhook URL en la consola de Twilio para ese número
- Los clientes simplemente mandan mensaje a tu +52 33 2101 6770 por WhatsApp y hablan con el agente

**Costos:**
- Twilio: ~$0.005-0.008/mensaje
- Meta: ~$0.03-0.08/conversación de 24h (dependiendo de quién inicia)
- Estimado 100 conversaciones/mes: ~$5-10 USD

---

## Implementación en código

### Nuevo adapter: `src/app/channels/twilio_whatsapp.py`

El adapter de Twilio WhatsApp es MÁS SIMPLE que el de Meta porque:
- Mismo formato que SMS (flat form-encoded, no JSON anidado)
- No hay verify challenge (usa firma HMAC en header)
- Auth por HTTP Basic (SID:Token permanentes)

```python
class TwilioWhatsAppAdapter(ChannelAdapter):
    """WhatsApp via Twilio — same API as SMS with 'whatsapp:' prefix."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str, http_client):
        self._sid = account_sid
        self._token = auth_token
        self._from = f"whatsapp:{from_number}"
        self._client = http_client
        self._base_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}"

    @property
    def channel_name(self) -> str:
        return "twilio_whatsapp"

    def parse_incoming(self, form_data: dict[str, str]) -> IncomingMessage | None:
        # form_data viene de request.form() (no JSON)
        body = form_data.get("Body", "")
        from_number = form_data.get("From", "").removeprefix("whatsapp:")
        message_sid = form_data.get("MessageSid", "")
        num_media = int(form_data.get("NumMedia", "0"))

        media_id = ""
        media_type = ""
        if num_media > 0:
            media_id = form_data.get("MediaUrl0", "")
            media_type = form_data.get("MediaContentType0", "")

        return IncomingMessage(
            channel="twilio_whatsapp",
            sender_id=from_number,
            message=body,
            message_id=message_sid,
            media_id=media_id,
            media_type="audio" if "audio" in media_type else media_type,
        )

    async def send_reply(self, message: OutgoingMessage) -> tuple[bool, int]:
        # POST to Twilio Messages API with Basic Auth
        ...

    async def download_media(self, media_url: str) -> bytes | None:
        # GET media_url with Basic Auth
        ...
```

### Nuevo webhook route:

```
POST /webhook/twilio-whatsapp/{tenant_id}
```

- Content-Type: `application/x-www-form-urlencoded` (no JSON)
- Parse con `await request.form()`
- Validar firma: header `X-Twilio-Signature` (HMAC-SHA1)
- El resto del flujo es igual que el WhatsApp Meta: dedup, rate limit, process agent

### Diferencias clave vs Meta Cloud API:

| Aspecto | Meta (actual) | Twilio WhatsApp (nuevo) |
|---------|--------------|------------------------|
| Webhook Content-Type | `application/json` | `application/x-www-form-urlencoded` |
| Parse | `request.json()` | `request.form()` |
| Auth de envío | Bearer token | HTTP Basic Auth |
| Send endpoint | `graph.facebook.com` | `api.twilio.com/.../Messages.json` |
| Media download | Bearer + media ID → URL | Basic Auth + direct URL |
| Verify webhook | Challenge/response GET | HMAC signature header |
| From/To format | plain numbers | `whatsapp:+52...` prefix |

### Archivos a crear/modificar:

| Archivo | Cambio |
|---------|--------|
| `src/app/channels/twilio_whatsapp.py` | **NUEVO** — adapter |
| `src/app/api/routes/webhook_twilio_wa.py` | **NUEVO** — webhook route |
| `src/app/db/models.py` | Agregar campo `twilio_whatsapp_number` a TenantCredentials (o reusar twilio_phone_number) |
| `src/app/main.py` | Registrar nueva ruta |
| `src/app/middleware/auth.py` | Agregar `/webhook/twilio-whatsapp` a EXCLUDED_PREFIXES |
| `tests/test_twilio_wa.py` | **NUEVO** |

### Credentials por tenant (ya en DB):

Los campos `twilio_account_sid`, `twilio_auth_token_enc`, `twilio_phone_number` en `TenantCredentials` ya existen y sirven perfectamente para este canal.

---

## Resumen de prioridades

1. **Para demostrar HOY:** Usa el Sandbox — 5 minutos de setup, los clientes hacen "join" y hablan
2. **Para producción:** Registra el sender (necesitas Meta Business Portfolio) — 1-5 días de aprobación
3. **Para implementar:** ~1 día de código (adapter + ruta + tests). Es más simple que el Meta adapter actual.

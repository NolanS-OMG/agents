# Investigación de Proveedores — Fase 4

## 1. Proveedores LLM para Producción

### Comparativa de Precios (por 1M tokens, julio 2025)

| Proveedor | Modelo recomendado | Input | Output | Latencia | Tool Calling | Free Tier | Español |
|-----------|--------------------|-------|--------|----------|--------------|-----------|---------|
| **Mistral** | Small 4 | $0.15 | $0.60 | Rápida | Sí | Sí | Bueno |
| **OpenAI** | gpt-5.4-nano | $0.20 | $1.25 | Rápida | Sí | Créditos limitados | Bueno |
| **Google** | Gemini 2.5 Flash | $0.30 | $2.50 | Rápida | Sí | Generoso | Bueno |
| **Groq** | Llama 3.3 70B | $0.59 | $0.79 | Ultra-rápida | Limitado | Sí | Aceptable |
| **Anthropic** | Claude Haiku 4.5 | $1.00 | $5.00 | Rápida | Sí | No | Bueno |
| **Together AI** | Llama 3.3 70B | $1.04 | $1.04 | Rápida | Sí | Créditos | Aceptable |
| **Mistral** | Large 3 | $0.50 | $1.50 | Media | Sí | Sí | Bueno |
| **Anthropic** | Claude Sonnet 5 | $2.00 | $10.00 | Rápida | Sí | No | Bueno |
| **Cerebras** | Llama (custom) | ~$0.50 | ~$1.00 | Ultra-rápida | Limitado | $5 créditos | Aceptable |
| **Azure OpenAI** | Mismos que OpenAI | Igual | Igual | Rápida | Sí | $200 créditos | Bueno |

### Costo mensual estimado: Bot restaurante (200 conv/día, 5 turnos, 500 tokens/turno)

~45M tokens input + ~6M tokens output por mes.

| Modelo | Costo/mes |
|--------|-----------|
| Mistral Small 4 | ~$10 |
| GPT-5.4-nano | ~$17 |
| Gemini 2.5 Flash | ~$28 |
| Groq Llama 3.3 70B | ~$31 |
| Claude Haiku 4.5 | ~$75 |
| Claude Sonnet 5 | ~$150 |

### Recomendación por escenario

| Escenario | Proveedor | Razón |
|-----------|-----------|-------|
| **Prototipo/desarrollo** | Google Gemini free tier | Gratis, generoso, buen tool calling |
| **Producción económica** | Mistral Small 4 | $10/mes, empresa francesa con buen multilingüe |
| **Mejor relación calidad/precio** | Gemini 2.5 Flash | $28/mes, excelente en español y tool calling |
| **Máxima velocidad** | Groq (Llama 3.3) | Sub-segundo, pero tool calling limitado |
| **Máxima calidad** | Claude Haiku 4.5 / GPT-5.4-nano | Mejor seguimiento de instrucciones y estilo |

---

## 2. WhatsApp Business API

### Meta Cloud API (Directo)

**Modelo de precios (desde julio 2025):** Precio por mensaje, no por conversación.

| Tipo | Costo (México) |
|------|----------------|
| Respuestas no-template (dentro de 24h) | **GRATIS** |
| Templates utilitarios (en ventana de servicio) | **GRATIS** |
| Templates de marketing | ~$0.036 USD/msg |
| Templates utilitarios (fuera de ventana) | ~$0.008 USD/msg |
| Templates de autenticación | ~$0.003 USD/msg |

**Requisitos:**
- Meta Business Account verificado
- Número telefónico +52 (verificación por SMS o llamada)
- Meta App Dashboard con permisos `whatsapp_business_messaging`
- Endpoint webhook para recibir mensajes

**Rate limits:** 80 msg/segundo. Cuentas nuevas: 250 mensajes iniciados por negocio/24h, escala a 1K, 10K, ilimitado.

**Tipos de mensaje:** Texto, templates con variables, botones interactivos (hasta 3), listas (hasta 10 secciones), media, ubicación, contactos, reacciones.

### BSPs (Business Solution Providers)

| Proveedor | Costo mensual | Markup/msg | Free tier | SDK Python |
|-----------|---------------|------------|-----------|------------|
| **Meta directo** | $0 | $0 | Replies gratis | REST simple |
| **Twilio** | $0 | $0.005 + Meta | ~$15 trial | Excelente |
| **360dialog** | $59/mes | Solo Meta fees | Sandbox | REST, libs community |
| **Gupshup** | Contactar | ~$0.001-0.005 | 1,000 msgs | REST |
| **Wati** | $39-99/mes | Incluido | 7 días trial | REST |
| **MessageBird** | Pay-as-you-go | ~$0.005 + Meta | Sandbox | SDK Python |
| **Vonage** | $0 | $0.0063 + Meta | EUR 2 trial | SDK Python |

### Recomendación

**Para nuestro caso:** Meta Cloud API directo. Sin markup, respuestas gratis, y la integración son simples llamadas HTTP. Solo necesitas un BSP (Twilio) si quieres onboarding más rápido o soporte multi-canal desde un solo SDK.

**Costo real para bot de restaurante (~10K mensajes inbound/mes):** Efectivamente $0 si solo respondes (no-template). $80-360/mes si envías marketing proactivo.

### Open Source (Unofficial)

| Librería | Viable para producción? |
|----------|------------------------|
| Baileys (WhiskeySockets) | **NO** — viola ToS, baneos frecuentes |
| whatsapp-web.js | **NO** — mismo problema |

No son opción para un negocio real.

---

## 3. Canales Alternativos

| Canal | Costo | Integración (1-5) | Alcance en México | Rich messages |
|-------|-------|-------------------|-------------------|---------------|
| **WhatsApp** | Gratis (replies) | 4 | Altísimo (~95%) | Botones, listas, media |
| **Facebook Messenger** | Gratis | 4 | Alto (~93M users) | Botones, quick replies, menú |
| **Web Chat (Chatwoot)** | Gratis (self-hosted) | 3 | Universal (web) | Control total |
| **Web Chat (Tawk.to)** | Gratis | 5 | Universal | Widget pre-hecho |
| **Telegram** | Gratis | 5 | Bajo (~15%) | Keyboards, pagos, archivos |
| **Instagram DMs** | Gratis | 3 | Alto (~45M users) | Limitado (texto, imágenes, quick replies) |
| **SMS (Twilio)** | $0.03-0.05/msg | 4 | Universal | Solo texto (160 chars) |

### Notas clave

- **Facebook Messenger** usa la misma Graph API que WhatsApp. Sin costo para replies en 24h. Más fácil que WhatsApp (no necesita BSP).
- **Telegram** es ideal para prototipar — cero costo, cero aprobación, bot listo en 2 minutos via @BotFather.
- **Instagram DMs** requiere Business Account, no permite mensajes proactivos, sin carousels.
- **Web chat** con Chatwoot o custom WebSocket es el complemento ideal para sitio web.
- **SMS** solo como fallback o para notificaciones tipo "tu pedido está listo".

### Estrategia recomendada para México

1. **WhatsApp** como canal principal (95% de penetración)
2. **Facebook Messenger** como segundo canal (gratis, misma API)
3. **Web chat** (Chatwoot embebido) para el sitio web
4. **Telegram** para testing rápido durante desarrollo

---

## 4. Estrategia de Implementación

### Para desarrollo inmediato (Fase 4)

| Componente | Elección | Razón |
|------------|----------|-------|
| LLM | Gemini 2.5 Flash (free tier) | Prototipar gratis, migrar después |
| Canal de prueba | Telegram Bot | Gratis, instantáneo, sin aprobación |
| Canal producción | Meta WhatsApp Cloud API directo | Sin markup, replies gratis |
| Web chat | WebSocket custom o Chatwoot | Para el sitio del negocio |

### Para producción (cuando haya cliente pagando)

| Componente | Elección | Razón |
|------------|----------|-------|
| LLM | Mistral Small 4 o Gemini Flash | $10-28/mes para 200 conv/día |
| WhatsApp | Meta Cloud API directo | $0 para replies |
| Fallback LLM | OpenRouter multi-model | Si un proveedor cae, redirige |

### Costo total estimado de operación (producción, 200 conv/día)

| Concepto | Costo/mes |
|----------|-----------|
| LLM (Mistral Small) | $10 |
| WhatsApp (solo replies) | $0 |
| Servidor (VPS básico) | $5-20 |
| Redis | Incluido en VPS |
| **Total** | **$15-30 USD/mes** |

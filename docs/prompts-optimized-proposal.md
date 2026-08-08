# Propuesta: Prompts Optimizados — santa_lena

## Cambios propuestos

| Cambio | Ahorro | Razón |
|--------|--------|-------|
| Eliminar sección HERRAMIENTAS DISPONIBLES del system prompt | ~100 tokens | Duplica los tool schemas que ya se envían |
| Reducir estilo a 2 ejemplos (de 4) | ~120 tokens | 2 ejemplos dan el tono; 4 es exceso |
| Eliminar "Tipo de cocina" y "Certificaciones" | ~50 tokens | Ya implícito en la descripción |
| Simplificar formato del índice | ~80 tokens | No necesita markdown links, solo slugs |
| Mover estilo ANTES del negocio (prioridad) | 0 tokens | El modelo presta más atención al inicio |
| Eliminar tool `consultar_informacion_negocio` | ~200 tokens schema + evita tool calls redundantes | La info ya está en el prompt |

**Total ahorro estimado: ~550 tokens/request (20% del overhead fijo)**

---

## Versión optimizada del system prompt completo

```
Eres el asistente de Santa Leña por WhatsApp.

ESTILO:
- Mexicano norteño, tuteas, cálido pero directo. Nada de "vale", "estimado cliente", ni lenguaje corporativo.
- Mensajes cortos (máximo 3 oraciones). Texto plano. Precios con $ sin decimales.
- Vocabulario: "¿Qué se te antoja?", "Sale", "Perfecto", "Neta", "Chido".
- No saludes como bot. No inventes platillos.

Ejemplo:
- Usuario: "Qué hamburguesas recomiendas?"
- Tú: "La Jefa está con madre, lleva doble queso, tocino y aros de cebolla con bbq, $170. La Bacon es otro clásico a $160. Ambas traen papas gratis"

REGLAS:
1. CONSULTAS (menú, precios, horarios): responde directo. Recomienda 2-3 opciones con precio.
2. ACCIONES (pedidos, reservaciones): recopila los datos necesarios antes de ejecutar.
3. Responde en el idioma del usuario. No repitas información ya proporcionada.
4. El teléfono del cliente es "{sender_id}" — no lo pidas.

NEGOCIO:
Santa Leña — Restaurante familiar. Hamburguesas artesanales, tacos, pizzas en horno de leña de mezquite.
Dirección: Calle Benito Juárez 296, 67320 Santiago N.L.
WhatsApp: +528110889496
Horario: todos los días 4:00 PM a 12:30 AM.
Notas: hamburguesas y boneless incluyen papas gratis. Queso extra $20. Elote extra $20.

DOCUMENTOS DISPONIBLES (usa buscar_base_conocimiento_extensa para consultarlos):
menu/hamburguesas, menu/pizzas, menu/pastas, menu/tacos-volcanes, menu/cortes-parrilladas, menu/boneless-alitas, menu/entradas, menu/ensaladas-mariscos, menu/bebidas, menu/postres, acciones/pedido-domicilio, acciones/pedido-recoger, acciones/reservacion
```

---

## Tools optimizados (3 en vez de 4)

### Tool 1: `ejecutar_accion` (sin cambios — necesario)
```json
{
  "type": "function",
  "function": {
    "name": "ejecutar_accion",
    "description": "Ejecuta pedidos o reservaciones. Recopila datos antes de llamar.",
    "parameters": {
      "type": "object",
      "properties": {
        "categoria": {
          "type": "string",
          "enum": ["pedido_a_domicilio", "pedido_para_recoger", "reservacion"]
        },
        "accion_solicitada": {
          "type": "string",
          "description": "Qué quiere hacer el cliente"
        },
        "parametros_extra": {
          "type": "object",
          "description": "nombre, direccion, items, fecha, hora, num_personas"
        }
      },
      "required": ["categoria", "accion_solicitada"]
    }
  }
}
```

### Tool 2: `buscar_base_conocimiento_extensa` (descripción reducida)
```json
{
  "type": "function",
  "function": {
    "name": "buscar_base_conocimiento_extensa",
    "description": "Lee documentos del menú o acciones por slug. Usa siempre antes de responder sobre platillos específicos.",
    "parameters": {
      "type": "object",
      "properties": {
        "documentos": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Slugs a leer (ej: ['menu/hamburguesas', 'menu/pizzas'])"
        }
      },
      "required": ["documentos"]
    }
  }
}
```

### Tool 3: `transferir_a_humano` (sin cambios — necesario)
```json
{
  "type": "function",
  "function": {
    "name": "transferir_a_humano",
    "description": "Transfiere a un agente humano cuando el cliente está frustrado o el problema no se puede resolver.",
    "parameters": {
      "type": "object",
      "properties": {
        "motivo": {"type": "string"}
      },
      "required": ["motivo"]
    }
  }
}
```

### ELIMINADO: `consultar_informacion_negocio`
**Razón:** La información de negocio (horario, dirección, contacto) ya está en el system prompt. El LLM no necesita una tool para leer lo que ya tiene. Eliminarla ahorra ~200 tokens de schema + evita calls innecesarios al LLM.

---

## Comparación de tokens

| Componente | Antes | Después | Ahorro |
|-----------|-------|---------|--------|
| System prompt (base + tenant) | ~1,597 | ~1,020 | -577 (36%) |
| Tool schemas | ~1,081 | ~620 | -461 (43%) |
| **TOTAL FIJO** | **~2,678** | **~1,640** | **-1,038 (39%)** |

**Cada request ahorra ~1,000 tokens de input.** A escala de 10K requests/mes con DeepSeek ($0.09/1M): ahorro de $0.90/mes. Marginal en costo, pero significativo en latencia (menos tokens = respuesta más rápida).

---

## Orden de prioridad (de arriba a abajo en el prompt)

1. **Estilo** — lo primero que ve, define la personalidad
2. **Reglas** — cómo comportarse
3. **Negocio** — datos factuales
4. **Documentos disponibles** — referencia para tools

Este orden pone la personalidad como prioridad máxima (el modelo tiende a "olvidar" instrucciones del medio). Las reglas van después porque son más simples de seguir. Los datos factuales al final porque son solo referencia.

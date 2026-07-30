# Diseño: Base de Conocimiento por Tenant en PostgreSQL

## Qué tenemos hoy (filesystem OKF)

```
data/tenants/santa_lena/
├── index.md                    ← Bundle index con links a todos los docs
├── negocio/
│   ├── info-general.md         ← type: Negocio (horarios, ubicación)
│   └── promociones.md          ← type: Promociones
├── menu/
│   ├── hamburguesas.md         ← type: Menú
│   ├── pizzas.md               ← type: Menú
│   └── ...
├── acciones/
│   ├── pedido-domicilio.md     ← type: Acción (campos_requeridos, confirmación)
│   ├── pedido-recoger.md
│   └── reservacion.md
└── estilos/
    ├── chat.md                 ← type: Estilo (tono, vocabulario, ejemplos)
    └── voz.md
```

Cada archivo tiene:
- **Frontmatter YAML:** type, title, description, tags, status
- **Body Markdown:** contenido libre (tablas de menú, instrucciones de estilo, campos de acciones)

### Cómo se usa

1. **System prompt:** `get_prompt(estilo)` → combina info-general + promociones + índice + estilo
2. **Tool RAG:** `buscar_base_conocimiento_extensa` → busca en el body de los documentos por categoría
3. **Tool acciones:** `get_acciones_config()` → extrae campos requeridos/opcionales de las tablas

---

## Diseño en PostgreSQL

### Tabla: `knowledge_documents`

```sql
CREATE TABLE knowledge_documents (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    
    -- Identidad
    slug TEXT NOT NULL,                  -- "menu/hamburguesas" (path relativo)
    doc_type TEXT NOT NULL,              -- "menu", "accion", "estilo", "negocio", "promociones"
    title TEXT NOT NULL,                 -- "Hamburguesas"
    description TEXT DEFAULT '',
    
    -- Contenido
    body TEXT NOT NULL,                  -- El markdown completo (sin frontmatter)
    
    -- Metadata estructurada (reemplaza frontmatter)
    tags TEXT[] DEFAULT '{}',
    status TEXT DEFAULT 'stable',        -- stable, draft, archived
    
    -- Para acciones: campos extraídos
    campos_requeridos TEXT[] DEFAULT '{}',
    campos_opcionales TEXT[] DEFAULT '{}',
    confirmacion_requerida BOOLEAN DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Unicidad: un tenant no puede tener dos docs con el mismo slug
    UNIQUE(tenant_id, slug)
);

CREATE INDEX idx_kd_tenant_type ON knowledge_documents(tenant_id, doc_type);
CREATE INDEX idx_kd_tenant_tags ON knowledge_documents USING GIN(tags);
```

### Tabla: `tenant_prompts`

```sql
CREATE TABLE tenant_prompts (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    
    estilo TEXT NOT NULL,                -- "chat", "voz", "formal"
    system_prompt TEXT NOT NULL,         -- El prompt base personalizado
    
    -- Componentes del prompt (se concatenan)
    tono TEXT DEFAULT '',               -- Instrucciones de tono
    formato TEXT DEFAULT '',            -- Formato de respuesta
    vocabulario TEXT DEFAULT '',        -- Palabras a usar/evitar
    ejemplos TEXT DEFAULT '',           -- Ejemplos de conversación
    restricciones TEXT DEFAULT '',      -- Lo que NO debe hacer
    
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(tenant_id, estilo)
);
```

---

## Cómo se mapeа el filesystem → PostgreSQL

| Archivo actual | doc_type | slug |
|---------------|----------|------|
| negocio/info-general.md | negocio | negocio/info-general |
| negocio/promociones.md | promociones | negocio/promociones |
| menu/hamburguesas.md | menu | menu/hamburguesas |
| menu/pizzas.md | menu | menu/pizzas |
| acciones/pedido-domicilio.md | accion | acciones/pedido-domicilio |
| estilos/chat.md | — | → tabla `tenant_prompts` |

Los **estilos** no van a `knowledge_documents` — van a `tenant_prompts` porque son la definición del prompt del agente, no contenido buscable.

---

## Cómo funciona el nuevo TenantConfig

```python
class TenantConfig:
    """Carga la configuración del tenant desde PostgreSQL."""
    
    def __init__(self, tenant_id: str, docs: list[KnowledgeDocument], prompt: TenantPrompt):
        self.tenant_id = tenant_id
        self._docs = docs
        self._prompt = prompt
    
    def get_prompt(self, estilo: str = "chat") -> str:
        """Construye el system prompt combinando info del negocio + estilo."""
        negocio = self._find_doc(doc_type="negocio")
        promos = self._find_doc(doc_type="promociones")
        parts = []
        if negocio:
            parts.append(negocio.body)
        if promos:
            parts.append(promos.body)
        parts.append(f"\nÍNDICE:\n{self._build_index()}")
        if self._prompt:
            parts.append(f"\nESTILO:\n{self._prompt.system_prompt}")
        return "\n\n".join(parts)
    
    def search_docs(self, query: str, doc_type: str | None = None) -> list[KnowledgeDocument]:
        """Para la tool RAG: buscar documentos por contenido."""
        results = []
        for doc in self._docs:
            if doc_type and doc.doc_type != doc_type:
                continue
            if query.lower() in doc.body.lower() or query.lower() in doc.title.lower():
                results.append(doc)
        return results
    
    def get_acciones_config(self) -> list[dict]:
        """Para la tool ejecutar_accion: extraer acciones disponibles."""
        return [
            {
                "categoria": doc.slug.split("/")[-1].replace("-", "_"),
                "nombre": doc.title,
                "campos_requeridos": doc.campos_requeridos,
                "campos_opcionales": doc.campos_opcionales,
                "confirmacion_requerida": doc.confirmacion_requerida,
            }
            for doc in self._docs if doc.doc_type == "accion"
        ]
```

---

## API para gestionar el conocimiento

```
# CRUD de documentos
POST   /api/v1/knowledge                   ← Crear documento
GET    /api/v1/knowledge                   ← Listar todos (del tenant autenticado)
GET    /api/v1/knowledge/{slug}            ← Leer un documento
PUT    /api/v1/knowledge/{slug}            ← Actualizar
DELETE /api/v1/knowledge/{slug}            ← Eliminar

# CRUD de prompts/estilos
POST   /api/v1/prompts                     ← Crear estilo
GET    /api/v1/prompts                     ← Listar estilos
PUT    /api/v1/prompts/{estilo}            ← Actualizar estilo
```

### Ejemplo: crear un documento de menú

```json
POST /api/v1/knowledge
Headers: X-API-Key: sk_santa_xxxxx

{
  "slug": "menu/hamburguesas",
  "doc_type": "menu",
  "title": "Hamburguesas",
  "description": "Hamburguesas de res y pollo",
  "body": "# Hamburguesas\n\n| Hamburguesa | Precio |\n|---|---|\n| Clásica | $130 |...",
  "tags": ["menu", "hamburguesas", "angus"]
}
```

### Ejemplo: crear una acción

```json
POST /api/v1/knowledge
{
  "slug": "acciones/pedido-domicilio",
  "doc_type": "accion",
  "title": "Pedido a Domicilio",
  "body": "# Pedido a Domicilio\n\nRegistra un pedido para entrega.",
  "campos_requeridos": ["nombre_cliente", "telefono", "direccion_entrega", "items_pedido"],
  "campos_opcionales": ["notas_especiales", "metodo_pago"],
  "confirmacion_requerida": true
}
```

### Ejemplo: crear/actualizar un estilo

```json
PUT /api/v1/prompts/chat
{
  "system_prompt": "Eres un mesero mexicano amable...",
  "tono": "Mexicano norteño. Tuteas. Nada de modismos españoles.",
  "formato": "Mensajes cortos. Máximo 3 oraciones.",
  "vocabulario": "Usa: 'qué onda', 'sale', 'neta', 'chido'. Evita: 'estimado cliente'.",
  "ejemplos": "Usuario: 'Hola'\nTú: 'Qué onda! ¿Qué se te antoja?'",
  "restricciones": "No inventes platillos. No uses lenguaje corporativo."
}
```

---

## Migración: filesystem → PostgreSQL

Script `scripts/migrate_okf_to_db.py`:

```python
# Lee todos los .md del filesystem
# Parsea frontmatter
# Inserta en knowledge_documents o tenant_prompts según el type
# Para acciones: extrae campos_requeridos del body
```

Esto se corre UNA VEZ para migrar santa_lena. Los nuevos tenants se crean directo en la DB.

---

## Ventajas vs filesystem

| Aspecto | Filesystem | PostgreSQL |
|---------|-----------|------------|
| Multi-tenant | Una carpeta por tenant | Una tabla con tenant_id |
| Búsqueda | Leer todos los archivos | WHERE + ILIKE / GIN index |
| CRUD remoto | SSH + editar archivos | API REST |
| Concurrencia | Lock de archivos | Transacciones |
| Backup | git / rsync | pg_dump / replicación |
| Auditoría | git log | updated_at + created_at |
| Escalabilidad | Miles de archivos = lento | Millones de rows = rápido |

---

## Caching

Cargar todos los docs de un tenant en cada request es ineficiente. Estrategia:

```python
# Redis cache con TTL de 5 minutos
# Key: tenant_config:{tenant_id}
# Invalidar al hacer PUT/POST/DELETE en /knowledge o /prompts

async def get_tenant_config(tenant_id: str) -> TenantConfig:
    cached = await redis.get(f"tenant_config:{tenant_id}")
    if cached:
        return deserialize(cached)
    
    docs = await KnowledgeDocument.filter(tenant_id=tenant_id, status="stable")
    prompt = await TenantPrompt.filter(tenant_id=tenant_id, active=True).first()
    config = TenantConfig(tenant_id, docs, prompt)
    
    await redis.setex(f"tenant_config:{tenant_id}", 300, serialize(config))
    return config
```

---

## Cosas que no cambian

- **El formato del body sigue siendo Markdown** — el contenido se almacena tal cual
- **Las tools siguen funcionando igual** — solo cambia de dónde se obtiene el TenantConfig
- **El LLM no sabe la diferencia** — recibe el mismo prompt armado
- **El AgentRouter no cambia** — sigue recibiendo un TenantConfig con los mismos métodos

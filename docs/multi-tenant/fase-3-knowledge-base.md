# Fase 3: Knowledge Base en PostgreSQL

## Objetivo

Migrar el sistema OKF de archivos a PostgreSQL, exponer CRUD via API, y que el AgentRouter/tools funcionen con datos de DB sin cambios en su interfaz.

---

## 3.1 Refactorizar TenantConfig

**Archivo:** `src/app/services/tenant.py` (reescribir)

El `TenantConfig` deja de leer archivos y recibe datos de DB:

```python
class TenantConfig:
    def __init__(self, tenant_id: str, docs: list, prompt: TenantPrompt | None):
        ...
    
    def get_prompt(self, estilo: str = "chat") -> str:
        # Si hay prompt en DB → usarlo
        # Si no → BASE_SYSTEM_PROMPT (fallback actual)
    
    def get_acciones_config(self) -> list[dict]:
        # Leer de docs donde doc_type == "accion"
        # campos_requeridos ya viene como array (no parsear tablas)
    
    def read_doc(self, ruta: str) -> str | None:
        # Buscar por slug
    
    def search_docs(self, query: str, doc_type: str | None = None) -> list:
        # Para la tool RAG
```

---

## 3.2 Carga con Cache

**Archivo nuevo:** `src/app/services/tenant_loader.py`

```python
async def load_tenant_config(tenant_id: str, redis) -> TenantConfig:
    # 1. Intentar cache Redis (key: tenant_config:{tenant_id})
    # 2. Si miss → cargar de DB
    # 3. Guardar en cache con TTL 5 min
    # 4. Retornar TenantConfig
```

Invalidación: cuando se hace POST/PUT/DELETE en `/knowledge` o `/prompts`, borrar la cache key.

---

## 3.3 Endpoints CRUD Knowledge

**Archivo nuevo:** `src/app/api/routes/knowledge.py`

```
POST   /api/v1/knowledge           ← Crear documento
GET    /api/v1/knowledge           ← Listar (por doc_type, tags)
GET    /api/v1/knowledge/{slug}    ← Leer uno
PUT    /api/v1/knowledge/{slug}    ← Actualizar
DELETE /api/v1/knowledge/{slug}    ← Eliminar (soft delete: status=archived)
```

Todos requieren auth (X-API-Key). El tenant_id se extrae del contexto.

---

## 3.4 Endpoints CRUD Prompts

**Archivo nuevo:** `src/app/api/routes/prompts.py`

```
POST   /api/v1/prompts             ← Crear estilo
GET    /api/v1/prompts             ← Listar estilos del tenant
GET    /api/v1/prompts/{estilo}    ← Leer uno
PUT    /api/v1/prompts/{estilo}    ← Actualizar
DELETE /api/v1/prompts/{estilo}    ← Desactivar
```

---

## 3.5 Fallback de Prompts

Si un tenant NO tiene prompt configurado para el estilo solicitado, usar el `BASE_SYSTEM_PROMPT` que ya existe en `agent_router.py`. Esto garantiza que el sistema funciona sin configuración custom.

```python
def get_prompt(self, estilo: str = "chat") -> str:
    if self._prompt:
        # Ensamblar desde componentes del prompt custom
        ...
    else:
        # Fallback: prompt genérico actual
        return ""  # AgentRouter ya tiene BASE_SYSTEM_PROMPT
```

---

## 3.6 Script de Migración

**Archivo nuevo:** `scripts/migrate_okf_to_db.py`

```python
# Lee data/tenants/santa_lena/**/*.md
# Parsea frontmatter + body
# Para type=Estilo → INSERT en tenant_prompts
# Para todo lo demás → INSERT en knowledge_documents
# Para type=Acción → extraer campos_requeridos del body y guardar como array
```

---

## 3.7 Tests

- Crear documento → leer → verificar body intacto
- Crear acción con campos → get_acciones_config() retorna los campos
- Buscar documento por query/doc_type
- Cache hit/miss (mock Redis)
- Fallback: tenant sin prompts usa BASE_SYSTEM_PROMPT
- Tools existentes funcionan con datos de DB

---

## Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `src/app/services/tenant.py` | Reescribir (cargar de DB) |
| `src/app/services/tenant_loader.py` | **NUEVO** (cache + load) |
| `src/app/api/routes/knowledge.py` | **NUEVO** |
| `src/app/api/routes/prompts.py` | **NUEVO** |
| `src/app/main.py` | Registrar routes |
| `scripts/migrate_okf_to_db.py` | **NUEVO** |
| `tests/test_knowledge.py` | **NUEVO** |
| `tests/test_tenant_config.py` | **NUEVO** |

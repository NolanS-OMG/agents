# Fase 7: Scripts de Gestión + Cleanup

## Objetivo

Poder operar el sistema sin tocar la DB directamente. Migrar santa_lena del filesystem a la DB. Cleanup automático.

---

## 7.1 Script: create_tenant.py

**Archivo nuevo:** `scripts/create_tenant.py`

```bash
uv run python scripts/create_tenant.py \
  --id santa_lena \
  --name "Santa Leña Restaurante" \
  --whatsapp-token "EAABxxxxxxx" \
  --whatsapp-phone-id "123456789" \
  --twilio-sid "ACxxxxxxx" \
  --twilio-token "xxxxxxx" \
  --twilio-number "+523321016770"
```

Output:
```
✓ Tenant 'santa_lena' creado
✓ Credentials encriptadas y guardadas
✓ API Key generada: sk_santa_le_a8f2c9d1e4b7xxxxx
  (guárdala, no se puede recuperar)
```

El script:
1. Crea row en `tenants`
2. Encripta y guarda en `tenant_credentials`
3. Genera API key, guarda hash en `api_keys`
4. Imprime la key raw (única vez visible)

---

## 7.2 Script: migrate_okf_to_db.py

**Archivo nuevo:** `scripts/migrate_okf_to_db.py`

```bash
uv run python scripts/migrate_okf_to_db.py --tenant santa_lena
```

Lee `data/tenants/santa_lena/` y:
1. Parsea cada `.md` (frontmatter + body)
2. Para `type: Estilo` → INSERT en `tenant_prompts`
3. Para `type: Acción` → INSERT en `knowledge_documents` con campos_requeridos extraídos
4. Para todo lo demás → INSERT en `knowledge_documents`

Es idempotente: si el slug ya existe, actualiza.

---

## 7.3 Script: rotate_api_key.py

```bash
uv run python scripts/rotate_api_key.py --tenant santa_lena
```

1. Desactiva la key actual
2. Genera nueva key
3. Imprime nueva key

---

## 7.4 Audio Cleanup

**Archivo nuevo:** `scripts/cleanup_audio.py`

```bash
uv run python scripts/cleanup_audio.py --max-age-hours 24
```

Borra archivos de `data/audio/` más viejos que N horas. Puede correrse con cron:
```
0 * * * * cd /app && uv run python scripts/cleanup_audio.py --max-age-hours 24
```

---

## 7.5 Actualizar Documentación

- `README.md` — nuevo setup con PostgreSQL, API keys, ejemplo de uso
- `.env.example` — todas las vars nuevas documentadas
- `docs/` — mover docs viejos de investigación a `docs/archive/`

---

## 7.6 Smoke Test End-to-End

**Archivo nuevo:** `scripts/smoke_test.py`

```bash
uv run python scripts/smoke_test.py --api-key sk_santa_le_xxxxx
```

Prueba:
1. GET /health → 200
2. POST /api/v1/converse (texto) → respuesta válida
3. GET /api/v1/knowledge → lista docs
4. GET /api/v1/usage → datos
5. Report: todo OK o qué falló

---

## Archivos a crear

| Archivo | Descripción |
|---------|-------------|
| `scripts/create_tenant.py` | Alta de tenant + API key |
| `scripts/migrate_okf_to_db.py` | Filesystem → PostgreSQL |
| `scripts/rotate_api_key.py` | Rotar key de un tenant |
| `scripts/cleanup_audio.py` | Borrar audio viejo |
| `scripts/smoke_test.py` | Prueba end-to-end |

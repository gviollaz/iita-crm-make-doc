# CLAUDE.md — IITA Make.com Scenarios Documentation System

## Sobre este repo

Este repo contiene los blueprints exportados de todos los escenarios Make.com de IITA (Instituto de Innovación y Tecnología Aplicada), junto con herramientas para sincronizar y documentar.

- **Organización:** IITA, Salta, Argentina
- **Make.com region:** us2 | **Team ID:** 954615
- **Supabase project:** Base de datos CRM + marketing multicanal
- **Frontend:** IITA-Proyectos/iitacrm (deploy en Vercel)

## Sistema de documentación automática

Este repo incluye un sistema para generar documentación de cada escenario Make.com. El flujo es:

```
autodoc_helper.py prepare  →  genera tareas en tasks/
Claude Code procesa cada tarea  →  genera docs en docs/scenarios/ y docs/findings/
autodoc_helper.py status  →  muestra progreso
```

### Comandos del helper

```powershell
# Preparar todo (dump schema + generar tareas)
python autodoc_helper.py setup

# Ver estado de documentación
python autodoc_helper.py status

# Ver siguiente escenario a documentar
python autodoc_helper.py next

# Preparar tarea para un escenario específico
python autodoc_helper.py prepare --id 3730131

# Preparar tareas para todos
python autodoc_helper.py prepare --all

# Marcar un escenario como documentado
python autodoc_helper.py complete --id 3730131
```

### Cómo documentar un escenario

Cuando el usuario pide documentar un escenario (por ID o "el siguiente"):

1. Leer el archivo de tarea: `tasks/{id}_task.json`
2. Este archivo contiene: el blueprint completo, metadatos del manifest, y el schema de BD
3. Generar DOS archivos:
   - `docs/scenarios/{id}_{nombre}.md` — documentación técnica
   - `docs/findings/{id}_{nombre}_findings.md` — hallazgos y recomendaciones
4. Ejecutar: `python autodoc_helper.py complete --id {id}`

### Cómo documentar en batch

Cuando el usuario pide "documenta los próximos N escenarios":

1. Ejecutar: `python autodoc_helper.py next --count N`
2. Para cada ID devuelto, seguir el proceso de documentación individual
3. Procesar UNO A LA VEZ para no exceder el contexto
4. Después de cada uno, limpiar contexto mental y continuar con el siguiente

---

## Arquitectura del sistema IITA en Make.com

### Categorías de escenarios

| Carpeta | Función | Ejemplos |
|---------|---------|----------|
| 1_entrada | Webhooks que reciben mensajes de canales | INPUT WhatsApp, Instagram, Messenger |
| 2_procesamiento | Crean registros en la BD | Create new interaction, conversation, save media |
| 3_preprocesamiento | Analizan media antes de generar respuesta | Media analysis con Vision API |
| 4_generacion | Generan respuestas con IA | Generate AI response |
| 6_aprobacion | Interface con Google Sheets para aprobación humana | Create Google Sheets records |
| 7_envio | Envían mensajes aprobados por cada canal | OUT WhatsApp, Instagram, Messenger, Dispatcher |
| 8_otros | Legacy, pruebas, herramientas auxiliares | Tools, integraciones viejas |

### Flujo general de un mensaje

```
Canal (WhatsApp/IG/Messenger)
  → [1_entrada] Webhook recibe mensaje
    → [2_procesamiento] Create new interaction (guarda en BD)
      → [3_preprocesamiento] Si tiene media → analizar con Vision
        → [4_generacion] Generate AI response
          → [6_aprobacion] Escribir en Google Sheet para revisión humana
            → [7_envio] Cuando se aprueba → Dispatcher → canal de salida
```

### Convenciones de la BD (Supabase)

**Constraint `chk_single_direction`:** La tabla `interactions` tiene un constraint que impone que cada fila usa SOLO `id_person_conversation` O `id_system_conversation`, nunca ambos. Los mensajes del usuario usan person_conversation. Los mensajes del operador/sistema usan system_conversation.

**Función `is_crm_user()`:** Función PostgreSQL desplegada el 2026-02-26 para seguridad RLS. 9 tablas PII la usan.

**Prefijo `mkt_` en funciones:** Las funciones PostgreSQL del módulo de marketing mantienen el prefijo histórico `mkt_`, aunque en docs, tareas y labels se usa la abreviatura MKTG.

**Sistema de marketing bulk (MKTG):** Campañas masivas via pg_cron + Make.com. Documentación en gviollaz/iita-system docs/marketing/README.md.

### Cómo leer un blueprint JSON de Make.com

Un blueprint tiene esta estructura:

```json
{
  "name": "Nombre del escenario",
  "flow": [
    {
      "id": 1,
      "module": "gateway:CustomWebHook",
      "mapper": {},
      "routes": [
        {
          "flow": [],
          "filter": {
            "name": "Nombre del filtro",
            "conditions": []
          }
        }
      ]
    }
  ]
}
```

**Tipos de módulos comunes:**
- `gateway:CustomWebHook` — Webhook de entrada
- `gateway:WebhookRespond` — Responder al webhook
- `builtin:BasicRouter` — Router con rutas condicionales
- `http:ActionSendData` — HTTP request (GET/POST/PATCH)
- `json:ParseJSON` — Parsear JSON string
- `json:TransformToJSON` — Convertir a JSON string
- `util:SetVariable` / `util:SetVariable2` — Variable temporal
- `util:FunctionAggregator` — Agregador
- `util:FunctionSleep` — Sleep/delay
- `builtin:BasicFeeder` — Iterator sobre array
- `google-sheets:*` — Operaciones Google Sheets
- `openai-gpt-4:*` — Llamadas a OpenAI
- `anthropic-claude:*` — Llamadas a Anthropic
- `supabase:*` — Operaciones Supabase directas
- `whatsapp-business-cloud:*` — WhatsApp nativo
- `facebook:*` / `facebookpages:*` — Facebook/Instagram
- `flow:CallScenario` — Llamar a otro escenario (subscenario)

**Para identificar qué hace cada módulo:**
1. Ver `module` para el tipo
2. Ver `mapper` para los parámetros (URLs, queries SQL, templates)
3. Ver `parameters` para conexiones y configuración
4. Ver `metadata.designer.name` para el nombre visible en Make.com

---

## Formato de documentación (docs/scenarios/)

Cada archivo de documentación debe seguir esta estructura:

- Encabezado con ID, categoría, estado, tipo de trigger, uso
- Descripción: 2-3 párrafos sobre qué hace y cómo encaja en el sistema
- Diagrama de flujo: representación ASCII del flow de módulos
- Tabla de módulos: ID, tipo, nombre, descripción de cada módulo
- Tablas de BD involucradas: tabla, operación, campos principales
- Dependencias: subscenarios, webhooks, conexiones
- Notas adicionales

## Formato de hallazgos (docs/findings/)

Cada archivo de hallazgos debe incluir:

- Resumen ejecutivo de 1 párrafo
- Tabla de hallazgos con: severidad (🔴🟡🟢ℹ️), categoría, descripción, impacto, recomendación
- Severidades: Crítico (pierde datos/errores), Medio (inconsistencia/mejora), Menor (optimización), Info (observación)
- Categorías: Bug, Seguridad, Consistencia, Performance, Error Handling, Observación

---

## Reglas importantes

1. **NUNCA hacer cambios en la BD de producción** sin análisis de impacto completo
2. **Los JSONs de blueprint son READ-ONLY** — este repo documenta, no modifica
3. **Un escenario a la vez** — procesar, guardar, marcar completado, luego el siguiente
4. **Si un escenario legacy/test tiene poco contenido**, generar una ficha mínima en vez de forzar documentación extensa
5. **Citar módulos por su ID numérico** (ej: "módulo 5") para que se pueda rastrear en Make.com

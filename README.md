# IITA CRM - Documentación Automática de Escenarios Make.com

Sistema para generar documentación técnica y hallazgos de los 118 escenarios Make.com del CRM de IITA, usando Claude Code como motor de análisis.

## ¿Qué problema resuelve?

Documentar 118 escenarios Make.com manualmente es inviable. Intentar hacerlo dentro de una conversación de Claude.ai se corta por límites de contexto. Este sistema lo resuelve procesando **un escenario a la vez** con Claude Code, con progreso persistente en disco.

## Arquitectura

```
autodoc_helper.py setup     →  Dump schema BD + genera 118 tareas individuales
Claude Code (via run_autodoc.ps1)  →  Procesa cada tarea → genera docs + hallazgos
autodoc_helper.py status    →  Muestra progreso (resumible si falla)
```

## Quick Start

Ver [SETUP_GUIDE.md](SETUP_GUIDE.md) para instrucciones detalladas.

```powershell
# 1. Instalar prerequisites
npm install -g @anthropic-ai/claude-code
pip install psycopg2-binary python-dotenv

# 2. Configurar
copy .env.example .env
# Editar .env con SUPABASE_DB_URL

# 3. Setup (dump schema + preparar tareas)
python autodoc_helper.py setup

# 4. Documentar
.\run_autodoc.ps1 -Count 5

# 5. Ver progreso
python autodoc_helper.py status
```

## Archivos Principales

| Archivo | Función |
|---------|--------|
| `CLAUDE.md` | Contexto persistente para Claude Code (arquitectura IITA, formatos, convenciones) |
| `autodoc_helper.py` | Helper Python: conexión BD, preparación de tareas, tracking de progreso |
| `run_autodoc.ps1` | Orquestador PowerShell que invoca Claude Code en loop |
| `SETUP_GUIDE.md` | Guía de instalación y uso paso a paso |
| `.env.example` | Template de variables de configuración |

## Estructura de Salida

```
docs/
├── scenarios/           # 1 archivo .md por escenario
│   ├── index.md
│   └── {id}_{nombre}.md
└── findings/            # Hallazgos separados
    ├── index.md
    └── {id}_{nombre}_findings.md
```

## Requisitos

- Node.js 18+ (para Claude Code)
- Python 3.10+
- Claude Code (`npm install -g @anthropic-ai/claude-code`)
- Cuenta Anthropic (Pro o Team)
- Acceso a la BD de Supabase (connection string)
- Repo [gviollaz/iita-make-scenarios](https://github.com/gviollaz/iita-make-scenarios) con snapshots

## Relación con otros repos

- **gviollaz/iita-make-scenarios**: Contiene los snapshots de blueprints y el `make_sync.py`. Los archivos de este repo se copian allí para ejecutar.
- **IITA-Proyectos/iitacrm**: Frontend del CRM (Vercel). No se modifica desde aquí.
- **gviollaz/iita-system**: Documentación general del sistema IITA.

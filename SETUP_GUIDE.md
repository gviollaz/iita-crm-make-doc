# Guía de Setup - Sistema de Documentación Automática

## Prerequisitos (instalar una vez)

### 1. Node.js 18+
Descargar de https://nodejs.org (versión LTS).
Verificar: `node --version`

### 2. Claude Code
```powershell
npm install -g @anthropic-ai/claude-code
```
Verificar: `claude --version`

La primera vez que lo ejecutes te va a pedir que te loguees con tu cuenta de Anthropic (la misma de claude.ai).

### 3. Python 3.10+
Ya lo tenés (usás make_sync.py). Verificar: `python --version`

### 4. Dependencias Python
```powershell
pip install psycopg2-binary python-dotenv
```

## Setup (5 minutos)

### Paso 1: Configurar .env
```powershell
cd C:\ruta\a\iita-make-scenarios
copy .env.example .env
```

Editar `.env` y agregar la connection string de Supabase:
```
SUPABASE_DB_URL=postgresql://postgres:TU_PASSWORD@db.TU_PROJECT.supabase.co:5432/postgres
```

La connection string la encontrás en:
Supabase Dashboard → Settings → Database → Connection string → URI

### Paso 2: Copiar archivos al repo iita-make-scenarios
Copiar estos archivos a la raíz de `iita-make-scenarios/`:
- `CLAUDE.md`
- `autodoc_helper.py`
- `run_autodoc.ps1`
- `.env.example` (renombrar a `.env` y completar)

### Paso 3: Ejecutar setup
```powershell
python autodoc_helper.py setup
```

Esto va a:
- Conectarse a la BD y extraer el schema (tablas, columnas, constraints, funciones)
- Preparar las 118 tareas de documentación (una por escenario)
- Crear las carpetas `docs/scenarios/`, `docs/findings/`, `tasks/`

### Paso 4: Verificar
```powershell
python autodoc_helper.py status
```

Deberías ver: 0/118 documentados, 118 tareas preparadas.

## Uso Diario

### Opción A: Uno a uno (recomendado para empezar)

```powershell
# Ver cuál es el siguiente
python autodoc_helper.py next

# Abrir Claude Code y pedirle que documente
claude

# Dentro de Claude Code, decirle:
# "Documentá el escenario 3730131 leyendo tasks/3730131_task.json"
```

### Opción B: Batch con el script PowerShell

```powershell
# Documentar los próximos 5
.\run_autodoc.ps1 -Count 5

# Documentar uno específico
.\run_autodoc.ps1 -Id 3730131

# Ver progreso
.\run_autodoc.ps1 -Status

# Dry run (simular sin ejecutar)
.\run_autodoc.ps1 -Count 10 -DryRun
```

### Opción C: Sesión interactiva de Claude Code

```powershell
claude
```

Y dentro de la sesión:
- "Documentá los próximos 3 escenarios pendientes"
- "Mostrá el estado con python autodoc_helper.py status"
- "Documentá todos los escenarios de la categoría 1_entrada"

Claude Code va a leer CLAUDE.md automáticamente y saber qué hacer.

## Después de documentar

```powershell
# Generar índice
python autodoc_helper.py index

# Subir al repo
git add docs/ autodoc_progress.json CLAUDE.md autodoc_helper.py
git commit -m "autodoc: documentación de N escenarios"
git push
```

## Troubleshooting

### "Claude Code se queda sin contexto"
Es normal si el blueprint es muy grande. El sistema está diseñado para procesar un escenario a la vez. Si uno falla, el progreso de los anteriores ya está guardado.

### "No se puede conectar a la BD"
Verificá que `SUPABASE_DB_URL` en `.env` es correcto. Podés probar con:
```powershell
python -c "import psycopg2; c=psycopg2.connect('TU_URL'); print('OK'); c.close()"
```

### "claude command not found"
Asegurate de que Node.js y Claude Code están en el PATH:
```powershell
$env:PATH
npm list -g @anthropic-ai/claude-code
```

### Quiero regenerar la doc de un escenario
Editar `autodoc_progress.json` y borrar la entrada del ID, luego:
```powershell
.\run_autodoc.ps1 -Id 3730131
```

### Quiero cambiar el snapshot base
Editar `AUTODOC_SNAPSHOT` en `.env` y ejecutar:
```powershell
python autodoc_helper.py prepare --all
```

## Estructura de Archivos

```
iita-make-scenarios/
├── CLAUDE.md                    # Contexto persistente para Claude Code
├── autodoc_helper.py            # Script Python helper
├── run_autodoc.ps1              # Orquestador PowerShell
├── autodoc_progress.json        # Progreso (generado automáticamente)
├── db_schema.json               # Schema de BD (generado por setup)
├── tasks/                       # Tareas de documentación (1 por escenario)
│   ├── 3502129_task.json
│   ├── 3730131_task.json
│   └── ...
├── docs/
│   ├── scenarios/               # Documentación generada
│   │   ├── index.md
│   │   └── ...
│   └── findings/                # Hallazgos generados
│       ├── index.md
│       └── ...
├── snapshots/                   # Blueprints exportados (ya existente)
├── make_sync.py                 # Herramienta de sync (ya existente)
└── .env                         # Configuración (no va al repo)
```

#!/usr/bin/env python3
"""
IITA Make.com Autodoc Helper
=============================
Herramienta auxiliar para el sistema de documentación automática de escenarios.

Uso:
    python autodoc_helper.py setup                    # Dump schema + preparar todo
    python autodoc_helper.py schema-dump              # Solo dump del schema de BD
    python autodoc_helper.py prepare --all             # Generar tareas para todos
    python autodoc_helper.py prepare --id 3730131      # Generar tarea para uno
    python autodoc_helper.py prepare --active-only     # Solo escenarios activos
    python autodoc_helper.py next                      # Ver siguiente a documentar
    python autodoc_helper.py next --count 5            # Ver próximos 5
    python autodoc_helper.py complete --id 3730131     # Marcar como documentado
    python autodoc_helper.py status                    # Ver progreso general
    python autodoc_helper.py status --verbose          # Progreso detallado

Requisitos:
    pip install psycopg2-binary python-dotenv
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Config ---
SNAPSHOT_DIR = os.environ.get("AUTODOC_SNAPSHOT", "snapshots/2026-02-26_produccion")
TASKS_DIR = "tasks"
DOCS_DIR = "docs/scenarios"
FINDINGS_DIR = "docs/findings"
PROGRESS_FILE = "autodoc_progress.json"
SCHEMA_FILE = "db_schema.json"
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")

# --- Progress tracking ---

def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed": {}, "errors": {}, "started_at": None, "last_updated": None}


def save_progress(progress):
    progress["last_updated"] = datetime.datetime.now().isoformat()
    if not progress.get("started_at"):
        progress["started_at"] = progress["last_updated"]
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def load_manifest():
    manifest_path = Path(SNAPSHOT_DIR) / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: No se encuentra {manifest_path}")
        print(f"Asegurate de que AUTODOC_SNAPSHOT apunte al snapshot correcto.")
        sys.exit(1)
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Database schema dump ---

def dump_schema():
    """Extrae el schema de la BD de Supabase y lo guarda en db_schema.json"""
    if not SUPABASE_DB_URL:
        print("WARN: SUPABASE_DB_URL no configurada. Generando schema vacío.")
        print("      Configurala en .env para enriquecer la documentación con info de BD.")
        schema = {"tables": [], "functions": [], "note": "Schema no disponible - configurar SUPABASE_DB_URL"}
        with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        return schema

    try:
        import psycopg2
    except ImportError:
        print("ERROR: Falta psycopg2. Instalalo con: pip install psycopg2-binary")
        sys.exit(1)

    print("Conectando a Supabase...")
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"ERROR conectando a la BD: {e}")
        print("Verificá SUPABASE_DB_URL en .env")
        sys.exit(1)

    # Tablas con columnas
    print("  Extrayendo tablas y columnas...")
    cur.execute("""
        SELECT 
            t.table_schema,
            t.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            col_description(
                (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass, 
                c.ordinal_position
            ) as column_comment
        FROM information_schema.tables t
        JOIN information_schema.columns c 
            ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE t.table_schema IN ('public', 'auth')
            AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_schema, t.table_name, c.ordinal_position
    """)
    
    tables_raw = cur.fetchall()
    tables = {}
    for schema, table, col, dtype, nullable, default, comment in tables_raw:
        key = f"{schema}.{table}"
        if key not in tables:
            tables[key] = {"schema": schema, "name": table, "columns": []}
        tables[key]["columns"].append({
            "name": col,
            "type": dtype,
            "nullable": nullable == "YES",
            "default": default,
            "comment": comment
        })

    # Constraints (PKs, FKs, checks)
    print("  Extrayendo constraints...")
    cur.execute("""
        SELECT 
            tc.table_schema,
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_schema AS ref_schema,
            ccu.table_name AS ref_table,
            ccu.column_name AS ref_column
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name 
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.table_schema = 'public'
        ORDER BY tc.table_name, tc.constraint_name
    """)
    
    constraints_raw = cur.fetchall()
    for schema, table, cname, ctype, col, ref_schema, ref_table, ref_col in constraints_raw:
        key = f"{schema}.{table}"
        if key in tables:
            if "constraints" not in tables[key]:
                tables[key]["constraints"] = []
            tables[key]["constraints"].append({
                "name": cname, "type": ctype, "column": col,
                "ref_table": f"{ref_schema}.{ref_table}" if ref_table else None,
                "ref_column": ref_col
            })

    # Check constraints
    print("  Extrayendo check constraints...")
    cur.execute("""
        SELECT 
            n.nspname as schema,
            r.relname as table_name,
            c.conname as constraint_name,
            pg_get_constraintdef(c.oid) as definition
        FROM pg_constraint c
        JOIN pg_class r ON c.conrelid = r.oid
        JOIN pg_namespace n ON r.relnamespace = n.oid
        WHERE c.contype = 'c' AND n.nspname = 'public'
        ORDER BY r.relname, c.conname
    """)
    
    checks_raw = cur.fetchall()
    for schema, table, cname, definition in checks_raw:
        key = f"{schema}.{table}"
        if key in tables:
            if "check_constraints" not in tables[key]:
                tables[key]["check_constraints"] = []
            tables[key]["check_constraints"].append({
                "name": cname,
                "definition": definition
            })

    # Enums
    print("  Extrayendo enums...")
    cur.execute("""
        SELECT 
            t.typname as enum_name,
            array_agg(e.enumlabel ORDER BY e.enumsortorder) as values
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        JOIN pg_namespace n ON t.typnamespace = n.oid
        WHERE n.nspname = 'public'
        GROUP BY t.typname
        ORDER BY t.typname
    """)
    enums = [{"name": name, "values": vals} for name, vals in cur.fetchall()]

    # Funciones públicas
    print("  Extrayendo funciones...")
    cur.execute("""
        SELECT 
            p.proname as name,
            pg_get_function_arguments(p.oid) as args,
            pg_get_function_result(p.oid) as return_type,
            d.description as comment
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        LEFT JOIN pg_description d ON p.oid = d.objoid
        WHERE n.nspname = 'public'
            AND p.prokind = 'f'
        ORDER BY p.proname
    """)
    functions = [{"name": n, "args": a, "returns": r, "comment": c} for n, a, r, c in cur.fetchall()]

    # RLS policies
    print("  Extrayendo políticas RLS...")
    cur.execute("""
        SELECT 
            schemaname,
            tablename,
            policyname,
            permissive,
            roles,
            cmd,
            qual,
            with_check
        FROM pg_policies
        WHERE schemaname = 'public'
        ORDER BY tablename, policyname
    """)
    policies_raw = cur.fetchall()
    rls_policies = {}
    for schema, table, policy, permissive, roles, cmd, qual, with_check in policies_raw:
        key = f"{schema}.{table}"
        if key not in rls_policies:
            rls_policies[key] = []
        rls_policies[key].append({
            "name": policy, "permissive": permissive,
            "roles": roles, "command": cmd,
            "using": qual, "with_check": with_check
        })

    # Ensamblar
    schema_data = {
        "extracted_at": datetime.datetime.now().isoformat(),
        "database_url": SUPABASE_DB_URL.split("@")[1] if "@" in SUPABASE_DB_URL else "***",
        "tables": list(tables.values()),
        "enums": enums,
        "functions": functions,
        "rls_policies": {k: v for k, v in rls_policies.items()},
        "table_count": len(tables),
        "function_count": len(functions),
        "enum_count": len(enums)
    }

    cur.close()
    conn.close()

    with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
        json.dump(schema_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n  Schema guardado en {SCHEMA_FILE}")
    print(f"  {len(tables)} tablas, {len(functions)} funciones, {len(enums)} enums")
    return schema_data


# --- Task preparation ---

def load_schema():
    if Path(SCHEMA_FILE).exists():
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def extract_tables_from_blueprint(blueprint):
    """Intenta extraer nombres de tablas mencionadas en el blueprint."""
    bp_str = json.dumps(blueprint).lower()
    schema = load_schema()
    if not schema or not schema.get("tables"):
        return []
    
    found = []
    for table in schema["tables"]:
        table_name = table["name"]
        if table_name.lower() in bp_str:
            found.append(table_name)
    return found


def get_relevant_schema(table_names, schema):
    """Extrae solo las tablas relevantes del schema completo."""
    if not schema or not schema.get("tables"):
        return None
    
    relevant = []
    for table in schema["tables"]:
        if table["name"] in table_names:
            relevant.append(table)
    return relevant


def prepare_task(scenario, snapshot_dir, schema):
    """Genera el archivo de tarea para un escenario."""
    sid = scenario["id"]
    filename = scenario["filename"]
    blueprint_path = Path(snapshot_dir) / filename
    
    if not blueprint_path.exists():
        print(f"  WARN: Blueprint no encontrado: {blueprint_path}")
        return False
    
    with open(blueprint_path, "r", encoding="utf-8") as f:
        blueprint = json.load(f)
    
    # Detectar tablas usadas
    table_names = extract_tables_from_blueprint(blueprint)
    relevant_schema = get_relevant_schema(table_names, schema) if schema else None
    
    # Detectar subscenarios llamados
    subscenarios = []
    bp_str = json.dumps(blueprint)
    if "CallScenario" in bp_str or "flow:CallScenario" in bp_str:
        import re
        scenario_refs = re.findall(r'"scenario":\s*"?(\d+)"?', bp_str)
        subscenarios = list(set(scenario_refs))
    
    # Contar módulos
    def count_modules(flow):
        count = 0
        if isinstance(flow, list):
            for item in flow:
                count += 1
                if "routes" in item:
                    for route in item["routes"]:
                        count += count_modules(route.get("flow", []))
        return count
    
    module_count = count_modules(blueprint.get("flow", []))
    
    task = {
        "scenario_id": sid,
        "scenario_name": scenario["name"],
        "category": scenario["category"],
        "is_active": scenario.get("is_active", False),
        "type": scenario.get("type", "scenario"),
        "module_count": module_count,
        "tables_detected": table_names,
        "subscenarios_detected": subscenarios,
        "blueprint": blueprint,
        "relevant_db_schema": relevant_schema,
        "prepared_at": datetime.datetime.now().isoformat()
    }
    
    # Guardar
    task_dir = Path(TASKS_DIR)
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / f"{sid}_task.json"
    
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2, ensure_ascii=False)
    
    return True


def prepare_tasks(scenario_filter=None, active_only=False):
    """Genera tareas para los escenarios seleccionados."""
    manifest = load_manifest()
    schema = load_schema()
    scenarios = manifest["scenarios"]
    
    if active_only:
        scenarios = [s for s in scenarios if s.get("is_active")]
    
    if scenario_filter:
        scenarios = [s for s in scenarios if s["id"] == scenario_filter]
    
    if not scenarios:
        print("No se encontraron escenarios con esos filtros.")
        return
    
    print(f"Preparando {len(scenarios)} tareas...")
    if not schema:
        print("WARN: Sin schema de BD. Ejecutá 'python autodoc_helper.py schema-dump' primero.")
    
    success = 0
    errors = 0
    for i, scenario in enumerate(scenarios, 1):
        name_short = scenario["name"][:50]
        print(f"  [{i}/{len(scenarios)}] {scenario['id']} {name_short}...", end=" ")
        try:
            if prepare_task(scenario, SNAPSHOT_DIR, schema):
                print("OK")
                success += 1
            else:
                print("SKIP")
                errors += 1
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
    
    print(f"\nPreparadas: {success} | Errores: {errors}")
    print(f"Tareas en: {TASKS_DIR}/")


# --- Status and navigation ---

def cmd_status(verbose=False):
    manifest = load_manifest()
    progress = load_progress()
    completed = progress.get("completed", {})
    scenarios = manifest["scenarios"]
    
    total = len(scenarios)
    done = len(completed)
    active_count = sum(1 for s in scenarios if s.get("is_active"))
    active_done = sum(1 for s in scenarios if s.get("is_active") and str(s["id"]) in completed)
    
    print(f"Estado de Documentación")
    print(f"=" * 50)
    print(f"  Total escenarios: {total}")
    print(f"  Documentados:     {done}/{total} ({done*100//total if total else 0}%)")
    print(f"  Pendientes:       {total - done}")
    print(f"")
    print(f"  Activos:          {active_done}/{active_count} documentados")
    print(f"  Inactivos:        {done - active_done}/{total - active_count} documentados")
    
    if progress.get("started_at"):
        print(f"\n  Iniciado:         {progress['started_at']}")
        print(f"  Última actividad: {progress['last_updated']}")
    
    if verbose:
        by_cat = {}
        for s in scenarios:
            cat = s["category"]
            is_done = str(s["id"]) in completed
            if cat not in by_cat:
                by_cat[cat] = {"total": 0, "done": 0, "pending": []}
            by_cat[cat]["total"] += 1
            if is_done:
                by_cat[cat]["done"] += 1
            else:
                by_cat[cat]["pending"].append(s)
        
        print(f"\nPor categoría:")
        for cat in sorted(by_cat.keys()):
            info = by_cat[cat]
            print(f"\n  [{cat}] {info['done']}/{info['total']}")
            if info["pending"]:
                for s in info["pending"][:5]:
                    status = "ON " if s.get("is_active") else "OFF"
                    print(f"    {status} [{s['id']}] {s['name']}")
                if len(info["pending"]) > 5:
                    print(f"    ... y {len(info['pending']) - 5} más")


def cmd_next(count=1):
    manifest = load_manifest()
    progress = load_progress()
    completed = progress.get("completed", {})
    
    scenarios = manifest["scenarios"]
    pending = [s for s in scenarios if str(s["id"]) not in completed]
    
    pending.sort(key=lambda s: (0 if s.get("is_active") else 1, s["category"], s["id"]))
    
    if not pending:
        print("¡Todos los escenarios están documentados! \ud83c\udf89")
        return []
    
    next_batch = pending[:count]
    print(f"Próximos {len(next_batch)} escenarios a documentar:")
    print()
    for s in next_batch:
        status = "ACTIVO" if s.get("is_active") else "INACTIVO"
        task_exists = "\u2705" if Path(TASKS_DIR, f"{s['id']}_task.json").exists() else "\u274c"
        print(f"  [{s['id']}] {s['name']}")
        print(f"    Categoría: {s['category']} | Estado: {status} | Tarea: {task_exists}")
    
    if len(next_batch) == 1:
        sid = next_batch[0]["id"]
        task_path = Path(TASKS_DIR) / f"{sid}_task.json"
        if task_path.exists():
            print(f"\n  Para documentar, decile a Claude Code:")
            print(f"    \"Documentá el escenario {sid} leyendo tasks/{sid}_task.json\"")
        else:
            print(f"\n  Primero prepará la tarea:")
            print(f"    python autodoc_helper.py prepare --id {sid}")
    
    return [s["id"] for s in next_batch]


def cmd_complete(scenario_id):
    progress = load_progress()
    
    docs_dir = Path(DOCS_DIR)
    findings_dir = Path(FINDINGS_DIR)
    
    doc_files = list(docs_dir.glob(f"{scenario_id}_*.md"))
    finding_files = list(findings_dir.glob(f"{scenario_id}_*.md"))
    
    if not doc_files:
        print(f"WARN: No se encontró documentación en {DOCS_DIR}/{scenario_id}_*.md")
        confirm = input("\u00bfMarcar como completado de todas formas? (s/n): ").strip().lower()
        if confirm != "s":
            print("Cancelado.")
            return
    
    progress["completed"][str(scenario_id)] = {
        "completed_at": datetime.datetime.now().isoformat(),
        "doc_file": str(doc_files[0]) if doc_files else None,
        "findings_file": str(finding_files[0]) if finding_files else None,
    }
    save_progress(progress)
    print(f"\u2705 Escenario {scenario_id} marcado como documentado.")
    
    manifest = load_manifest()
    total = len(manifest["scenarios"])
    done = len(progress["completed"])
    print(f"   Progreso: {done}/{total} ({done*100//total}%)")


# --- Setup ---

def cmd_setup():
    print("Setup del sistema de documentación automática")
    print("=" * 50)
    
    manifest_path = Path(SNAPSHOT_DIR) / "manifest.json"
    if manifest_path.exists():
        manifest = load_manifest()
        print(f"\n\u2705 Snapshot: {SNAPSHOT_DIR}")
        print(f"   {manifest['scenario_count']} escenarios")
    else:
        print(f"\n\u274c Snapshot no encontrado: {SNAPSHOT_DIR}")
        print(f"   Configurá AUTODOC_SNAPSHOT en .env o ejecutá make_sync.py export")
        return
    
    for d in [TASKS_DIR, DOCS_DIR, FINDINGS_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"\u2705 Directorio: {d}/")
    
    print(f"\n--- Schema de BD ---")
    schema = dump_schema()
    
    print(f"\n--- Preparando tareas ---")
    prepare_tasks()
    
    print(f"\n--- Listo ---")
    total = manifest["scenario_count"]
    task_count = len(list(Path(TASKS_DIR).glob("*_task.json")))
    print(f"\n  {task_count} tareas preparadas de {total} escenarios")
    print(f"\n  Próximo paso:")
    print(f"    1. Abrí Claude Code en este directorio")
    print(f"    2. Decile: \"Documentá el siguiente escenario\"")
    print(f"    3. O para batch: \"Documentá los próximos 5 escenarios\"")


# --- Generate index ---

def cmd_index():
    """Genera el índice consolidado de documentación."""
    manifest = load_manifest()
    progress = load_progress()
    completed = progress.get("completed", {})
    scenarios = manifest["scenarios"]
    
    docs_dir = Path(DOCS_DIR)
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    lines = [
        "# \u00cdndice de Documentaci\u00f3n de Escenarios Make.com\n",
        f"\n**Generado:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"\n**Snapshot:** {SNAPSHOT_DIR}",
        f"\n**Total:** {len(scenarios)} escenarios | **Documentados:** {len(completed)}\n",
    ]
    
    by_cat = {}
    for s in scenarios:
        cat = s["category"]
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(s)
    
    for cat in sorted(by_cat.keys()):
        lines.append(f"\n## {cat}\n")
        lines.append(f"\n| Estado | ID | Nombre | Activo | Doc |")
        lines.append(f"\n|--------|-----|--------|--------|-----|")
        for s in by_cat[cat]:
            is_done = "\u2705" if str(s["id"]) in completed else "\u2b1c"
            active = "\ud83d\udfe2" if s.get("is_active") else "\u26aa"
            doc_link = ""
            if str(s["id"]) in completed:
                doc_files = list(docs_dir.glob(f"{s['id']}_*.md"))
                if doc_files:
                    doc_link = f"[Ver]({doc_files[0].name})"
            lines.append(f"\n| {is_done} | {s['id']} | {s['name']} | {active} | {doc_link} |")
    
    index_path = docs_dir / "index.md"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    
    print(f"\u00cdndice generado: {index_path}")
    
    findings_dir = Path(FINDINGS_DIR)
    findings_dir.mkdir(parents=True, exist_ok=True)
    finding_files = sorted(findings_dir.glob("*_findings.md"))
    
    if finding_files:
        f_lines = [
            "# \u00cdndice de Hallazgos\n",
            f"\n**Generado:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
            f"\n**Total archivos:** {len(finding_files)}\n",
        ]
        for ff in finding_files:
            f_lines.append(f"\n- [{ff.stem}]({ff.name})")
        
        fi_path = findings_dir / "index.md"
        with open(fi_path, "w", encoding="utf-8") as f:
            f.write("".join(f_lines))
        print(f"\u00cdndice de hallazgos: {fi_path}")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="IITA Make.com Autodoc Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("setup", help="Setup completo: schema dump + preparar tareas")
    subparsers.add_parser("schema-dump", help="Extraer schema de la BD")
    
    prep_p = subparsers.add_parser("prepare", help="Preparar tareas de documentación")
    prep_p.add_argument("--id", type=int, help="ID de escenario específico")
    prep_p.add_argument("--all", action="store_true", help="Todos los escenarios")
    prep_p.add_argument("--active-only", action="store_true", help="Solo escenarios activos")
    
    next_p = subparsers.add_parser("next", help="Ver siguiente(s) escenario(s) a documentar")
    next_p.add_argument("--count", type=int, default=1, help="Cantidad a mostrar")
    
    comp_p = subparsers.add_parser("complete", help="Marcar escenario como documentado")
    comp_p.add_argument("--id", type=int, required=True, help="ID del escenario")
    
    stat_p = subparsers.add_parser("status", help="Ver progreso de documentación")
    stat_p.add_argument("--verbose", "-v", action="store_true", help="Detalle por categoría")
    
    subparsers.add_parser("index", help="Generar índice consolidado")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    commands = {
        "setup": lambda: cmd_setup(),
        "schema-dump": lambda: dump_schema(),
        "prepare": lambda: prepare_tasks(
            scenario_filter=args.id if hasattr(args, 'id') else None,
            active_only=getattr(args, 'active_only', False)
        ) if (getattr(args, 'id', None) or getattr(args, 'all', False) or getattr(args, 'active_only', False)) 
        else print("Especificá --id, --all, o --active-only"),
        "next": lambda: cmd_next(count=args.count),
        "complete": lambda: cmd_complete(args.id),
        "status": lambda: cmd_status(verbose=getattr(args, 'verbose', False)),
        "index": lambda: cmd_index(),
    }
    
    commands[args.command]()


if __name__ == "__main__":
    main()

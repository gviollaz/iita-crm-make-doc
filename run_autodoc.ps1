<# 
.SYNOPSIS
    IITA Make.com Autodoc - Orquestador PowerShell para Windows
.DESCRIPTION
    Ejecuta Claude Code en loop para documentar escenarios uno a uno.
    Cada escenario se procesa en una invocación independiente de Claude Code.
.EXAMPLE
    .\run_autodoc.ps1                    # Documenta el siguiente pendiente
    .\run_autodoc.ps1 -Count 5           # Documenta los próximos 5
    .\run_autodoc.ps1 -Id 3730131        # Documenta uno específico
    .\run_autodoc.ps1 -ActiveOnly        # Solo escenarios activos
    .\run_autodoc.ps1 -Status            # Ver progreso
    .\run_autodoc.ps1 -Setup             # Setup inicial
#>

param(
    [int]$Count = 1,
    [int]$Id = 0,
    [switch]$ActiveOnly,
    [switch]$Status,
    [switch]$Setup,
    [switch]$Index,
    [switch]$DryRun,
    [int]$PauseBetween = 5
)

$ErrorActionPreference = "Continue"

function Write-Success($msg) { Write-Host "  \u2705 $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  \u26a0\ufe0f  $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "  \u274c $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "  \u2139\ufe0f  $msg" -ForegroundColor Cyan }

function Test-Prerequisites {
    Write-Host "`n=== Verificando prerequisites ===" -ForegroundColor Cyan
    
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { Write-Success "Python: $($python.Source)" }
    else { Write-Err "Python no encontrado. Instalalo desde python.org"; return $false }
    
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if ($claude) { Write-Success "Claude Code: $($claude.Source)" }
    else { 
        Write-Err "Claude Code no encontrado."
        Write-Info "Instalalo con: npm install -g @anthropic-ai/claude-code"
        return $false 
    }
    
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) { Write-Success "Node.js: $(node --version)" }
    else { Write-Err "Node.js no encontrado (requerido por Claude Code)"; return $false }
    
    if (Test-Path "CLAUDE.md") { Write-Success "CLAUDE.md encontrado" }
    else { Write-Err "CLAUDE.md no encontrado en el directorio actual"; return $false }
    
    if (Test-Path "autodoc_helper.py") { Write-Success "autodoc_helper.py encontrado" }
    else { Write-Err "autodoc_helper.py no encontrado"; return $false }
    
    return $true
}

if ($Setup) {
    Write-Host "`n=== IITA Autodoc - Setup ===" -ForegroundColor Cyan
    if (-not (Test-Prerequisites)) { exit 1 }
    Write-Host "`nInstalando dependencias Python..."
    python -m pip install psycopg2-binary python-dotenv --quiet
    python autodoc_helper.py setup
    Write-Host "`n=== Setup completado ===" -ForegroundColor Green
    Write-Host "Pr\u00f3ximo paso: .\run_autodoc.ps1 -Count 1"
    exit 0
}

if ($Status) {
    python autodoc_helper.py status --verbose
    exit 0
}

if ($Index) {
    python autodoc_helper.py index
    exit 0
}

if (-not (Test-Prerequisites)) { exit 1 }

if ($Id -gt 0) {
    $scenarioIds = @($Id)
    Write-Host "`nDocumentando escenario espec\u00edfico: $Id" -ForegroundColor Cyan
} else {
    $nextOutput = python autodoc_helper.py next --count $Count 2>&1
    Write-Host $nextOutput
    
    $scenarioIds = @()
    foreach ($line in $nextOutput) {
        if ($line -match '^\s*\[(\d+)\]') {
            $scenarioIds += [int]$Matches[1]
        }
    }
    
    if ($scenarioIds.Count -eq 0) {
        Write-Info "No hay escenarios pendientes o no se pudieron extraer IDs."
        exit 0
    }
}

Write-Host "`n=== Procesando $($scenarioIds.Count) escenario(s) ===" -ForegroundColor Cyan
$startTime = Get-Date
$success = 0
$errors = 0

foreach ($sid in $scenarioIds) {
    $taskFile = "tasks/$($sid)_task.json"
    
    Write-Host "`n--- Escenario $sid ---" -ForegroundColor Yellow
    
    if (-not (Test-Path $taskFile)) {
        Write-Warn "Tarea no encontrada, preparando..."
        python autodoc_helper.py prepare --id $sid
        if (-not (Test-Path $taskFile)) {
            Write-Err "No se pudo preparar la tarea para $sid"
            $errors++
            continue
        }
    }
    
    $taskData = Get-Content $taskFile -Raw | ConvertFrom-Json
    $scenarioName = $taskData.scenario_name
    Write-Info "Nombre: $scenarioName"
    Write-Info "Categor\u00eda: $($taskData.category) | Activo: $($taskData.is_active)"
    Write-Info "M\u00f3dulos: $($taskData.module_count) | Tablas: $($taskData.tables_detected -join ', ')"
    
    if ($DryRun) {
        Write-Warn "DRY RUN - saltando generaci\u00f3n"
        continue
    }
    
    $prompt = @"
Lee el archivo tasks/$($sid)_task.json que contiene el blueprint y metadatos del escenario Make.com "$scenarioName" (ID: $sid).

Siguiendo las instrucciones en CLAUDE.md, gener\u00e1:

1. El archivo de documentaci\u00f3n en docs/scenarios/
2. El archivo de hallazgos en docs/findings/

Despu\u00e9s de generar ambos archivos, ejecut\u00e1:
python autodoc_helper.py complete --id $sid

IMPORTANTE: Us\u00e1 el formato exacto definido en CLAUDE.md. Analiz\u00e1 cada m\u00f3dulo del blueprint. Si es un escenario legacy/inactivo simple, gener\u00e1 una ficha resumida.
"@
    
    Write-Info "Invocando Claude Code..."
    $claudeStart = Get-Date
    
    try {
        $result = claude -p $prompt --no-input 2>&1
        $claudeEnd = Get-Date
        $duration = ($claudeEnd - $claudeStart).TotalSeconds
        
        $docFiles = Get-ChildItem "docs/scenarios/$($sid)_*" -ErrorAction SilentlyContinue
        $findingFiles = Get-ChildItem "docs/findings/$($sid)_*" -ErrorAction SilentlyContinue
        
        if ($docFiles) {
            Write-Success "Documentaci\u00f3n generada ($([math]::Round($duration))s)"
            $success++
        } else {
            Write-Err "Claude Code termin\u00f3 pero no gener\u00f3 el archivo de documentaci\u00f3n"
            Write-Host "  Output:" -ForegroundColor Gray
            $result | Select-Object -First 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            $errors++
        }
    }
    catch {
        Write-Err "Error ejecutando Claude Code: $_"
        $errors++
    }
    
    if ($scenarioIds.IndexOf($sid) -lt ($scenarioIds.Count - 1)) {
        Write-Info "Pausa de $PauseBetween segundos..."
        Start-Sleep -Seconds $PauseBetween
    }
}

$endTime = Get-Date
$totalDuration = ($endTime - $startTime).TotalMinutes

Write-Host "`n=== Resumen ===" -ForegroundColor Cyan
Write-Host "  Procesados: $($scenarioIds.Count)"
Write-Host "  Exitosos:   $success" -ForegroundColor Green
if ($errors -gt 0) { Write-Host "  Errores:    $errors" -ForegroundColor Red }
Write-Host "  Duraci\u00f3n:   $([math]::Round($totalDuration, 1)) minutos"

Write-Host ""
python autodoc_helper.py status

if ($success -gt 0) {
    Write-Host "`n  Para subir al repo:" -ForegroundColor Yellow
    Write-Host "    git add docs/ autodoc_progress.json"
    Write-Host "    git commit -m 'autodoc: $success escenarios documentados'"
    Write-Host "    git push"
}

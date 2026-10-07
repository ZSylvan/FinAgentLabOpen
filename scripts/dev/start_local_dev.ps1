[CmdletBinding()]
param(
    [switch]$SkipDependencyCheck
)

$ErrorActionPreference = 'Stop'

# This script starts only the Vue development server and the FastAPI server.
# MongoDB and Redis must already be running locally or through Docker.
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RuntimeDir = Join-Path $ProjectRoot 'runtime\local-dev'
$LogDir = Join-Path $ProjectRoot 'logs\local-dev'
$BackendPort = 8000
$FrontendPort = 3000

New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir | Out-Null

function Get-TrackedProcess {
    param([string]$Name)

    $recordPath = Join-Path $RuntimeDir "$Name.json"
    if (-not (Test-Path -LiteralPath $recordPath)) {
        return $null
    }

    try {
        $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
        if (-not $process) {
            Remove-Item -LiteralPath $recordPath -Force
            return $null
        }

        $expectedStart = ([datetime]$record.started_at).ToUniversalTime()
        $actualStart = $process.StartTime.ToUniversalTime()
        if ([math]::Abs(($actualStart - $expectedStart).TotalSeconds) -gt 1) {
            # The PID was reused by another process. Do not treat it as ours.
            Remove-Item -LiteralPath $recordPath -Force
            return $null
        }

        return [pscustomobject]@{
            Process = $process
            RecordPath = $recordPath
        }
    }
    catch {
        Remove-Item -LiteralPath $recordPath -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Test-PortAvailable {
    param([int]$Port, [string]$ServiceName)

    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        throw "$ServiceName needs port $Port, but PID $($listener.OwningProcess) is already using it. Stop that process first."
    }
}

function Save-ProcessRecord {
    param([string]$Name, [System.Diagnostics.Process]$Process, [string]$Command)

    [pscustomobject]@{
        pid        = $Process.Id
        started_at = $Process.StartTime.ToUniversalTime().ToString('o')
        command    = $Command
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeDir "$Name.json") -Encoding UTF8
}

function Wait-ForHttpService {
    param([string]$Url, [string]$Name)

    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "  $Name is ready: $Url" -ForegroundColor Green
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    Write-Host "  $Name is still starting or failed to start. Check the logs." -ForegroundColor Yellow
}

Write-Host 'Starting FinAgentLab local development environment' -ForegroundColor Cyan
Write-Host "Project directory: $ProjectRoot"

$backend = Get-TrackedProcess 'backend'
$frontend = Get-TrackedProcess 'frontend'

if ($backend) {
    Write-Host "Backend is already running (PID $($backend.Process.Id))." -ForegroundColor Yellow
}
else {
    Test-PortAvailable -Port $BackendPort -ServiceName 'Backend'
}

if ($frontend) {
    Write-Host "Frontend is already running (PID $($frontend.Process.Id))." -ForegroundColor Yellow
}
else {
    Test-PortAvailable -Port $FrontendPort -ServiceName 'Frontend'
}

if (-not $SkipDependencyCheck) {
    foreach ($dependency in @(
        @{ Name = 'MongoDB'; Port = 27017 },
        @{ Name = 'Redis'; Port = 6379 }
    )) {
        $available = Test-NetConnection -ComputerName '127.0.0.1' -Port $dependency.Port -InformationLevel Quiet -WarningAction SilentlyContinue
        if (-not $available) {
            Write-Host "Warning: $($dependency.Name) is not available at 127.0.0.1:$($dependency.Port). The backend may start, but related features will be unavailable." -ForegroundColor Yellow
        }
    }
}

if (-not $backend) {
    $pythonCandidates = @(
        (Join-Path $ProjectRoot '.venv\Scripts\python.exe'),
        (Join-Path $ProjectRoot 'venv\Scripts\python.exe')
    )
    $pythonExe = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $pythonExe) {
        $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
    if (-not $pythonExe) {
        throw 'Python was not found. Create the project virtual environment, or add python to PATH.'
    }

    $backendLog = Join-Path $LogDir 'backend.out.log'
    $backendErrorLog = Join-Path $LogDir 'backend.err.log'
    $backendArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', "$BackendPort", '--reload')
    $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList $backendArgs -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrorLog -WindowStyle Hidden -PassThru
    Save-ProcessRecord -Name 'backend' -Process $backendProcess -Command 'uvicorn app.main:app --reload'
    Write-Host "Backend started (PID $($backendProcess.Id))." -ForegroundColor Green
}

if (-not $frontend) {
    $viteCommand = Join-Path $ProjectRoot 'frontend\node_modules\.bin\vite.cmd'
    if (-not (Test-Path -LiteralPath $viteCommand)) {
        throw 'Frontend dependencies were not found. Run npm install in the frontend directory first.'
    }

    $frontendLog = Join-Path $LogDir 'frontend.out.log'
    $frontendErrorLog = Join-Path $LogDir 'frontend.err.log'
    $frontendArgs = @('--host', '0.0.0.0', '--port', "$FrontendPort")
    $frontendProcess = Start-Process -FilePath $viteCommand -ArgumentList $frontendArgs -WorkingDirectory (Join-Path $ProjectRoot 'frontend') `
        -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendErrorLog -WindowStyle Hidden -PassThru
    Save-ProcessRecord -Name 'frontend' -Process $frontendProcess -Command 'vite'
    Write-Host "Frontend started (PID $($frontendProcess.Id))." -ForegroundColor Green
}

Wait-ForHttpService -Url "http://127.0.0.1:$BackendPort/api/health" -Name 'Backend'
Wait-ForHttpService -Url "http://127.0.0.1:$FrontendPort" -Name 'Frontend'

Write-Host ''
Write-Host "Frontend: http://localhost:$FrontendPort" -ForegroundColor Cyan
Write-Host "Backend: http://localhost:$BackendPort" -ForegroundColor Cyan
Write-Host "API docs: http://localhost:$BackendPort/docs" -ForegroundColor Cyan
Write-Host "Logs: $LogDir" -ForegroundColor DarkGray
Write-Host "Stop command: .\scripts\dev\stop_local_dev.ps1" -ForegroundColor DarkGray

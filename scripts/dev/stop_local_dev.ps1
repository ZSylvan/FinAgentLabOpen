[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RuntimeDir = Join-Path $ProjectRoot 'runtime\local-dev'

function Stop-ProcessTree {
    param([int]$ProcessId, [System.Collections.Generic.HashSet[int]]$Visited)

    if (-not $Visited.Add($ProcessId)) {
        return
    }

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId ([int]$child.ProcessId) -Visited $Visited
    }

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -Force
    }
}

function Stop-TrackedService {
    param([string]$Name)

    $recordPath = Join-Path $RuntimeDir "$Name.json"
    if (-not (Test-Path -LiteralPath $recordPath)) {
        Write-Host "$Name was not started by the local development script." -ForegroundColor DarkGray
        return
    }

    try {
        $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        $processId = [int]$record.pid
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if (-not $process) {
            Write-Host "$Name process has already stopped." -ForegroundColor DarkGray
            return
        }

        $expectedStart = ([datetime]$record.started_at).ToUniversalTime()
        $actualStart = $process.StartTime.ToUniversalTime()
        if ([math]::Abs(($actualStart - $expectedStart).TotalSeconds) -gt 1) {
            Write-Host "$Name PID has been reused by another process. It will not be stopped." -ForegroundColor Yellow
            return
        }

        $visited = [System.Collections.Generic.HashSet[int]]::new()
        Stop-ProcessTree -ProcessId $processId -Visited $visited
        Write-Host "$Name stopped." -ForegroundColor Green
    }
    finally {
        Remove-Item -LiteralPath $recordPath -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $RuntimeDir)) {
    Write-Host 'No local development runtime records were found.' -ForegroundColor DarkGray
    exit 0
}

Stop-TrackedService -Name 'frontend'
Stop-TrackedService -Name 'backend'

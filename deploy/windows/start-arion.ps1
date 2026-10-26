param(
    [ValidateSet('web', 'worker')][string]$Role = 'web',
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$pythonw = Join-Path $ProjectRoot '.venv\Scripts\pythonw.exe'
$runner = Join-Path $ProjectRoot 'deploy\windows\run_process.py'
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'pythonw.exe da .venv não encontrado.' }
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'Supervisor do ARION não encontrado.' }

$process = Start-Process -FilePath $pythonw -ArgumentList @('"' + $runner + '"', $Role) `
    -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $python $runner --status $Role
if ($LASTEXITCODE -notin @(0, 1)) { throw 'Não foi possível confirmar o estado do processo.' }

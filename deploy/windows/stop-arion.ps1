param(
    [ValidateSet('web', 'worker')][string]$Role = 'web',
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$runner = Join-Path $ProjectRoot 'deploy\windows\run_process.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python da .venv não encontrado.' }
& $python $runner --stop $Role
if ($LASTEXITCODE -ne 0) { throw 'O supervisor não confirmou a parada dentro do limite.' }

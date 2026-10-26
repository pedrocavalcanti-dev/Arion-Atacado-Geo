param([string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)

$ErrorActionPreference = 'Stop'
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$runner = Join-Path $ProjectRoot 'deploy\windows\run_process.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python da .venv não encontrado.' }
foreach ($role in @('web', 'worker')) {
    & $python $runner --status $role
}
$cloudflared = Get-Service -Name 'Cloudflared' -ErrorAction SilentlyContinue
if ($cloudflared) {
    Write-Output "Cloudflared: $($cloudflared.Status)"
} else {
    Write-Output 'Cloudflared: Not installed'
}

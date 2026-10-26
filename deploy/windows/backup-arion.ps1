param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$BackupDirectory,
    [ValidateRange(0, 3650)][int]$RetentionDays = 30
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if (-not $BackupDirectory) { $BackupDirectory = Join-Path (Split-Path $ProjectRoot -Parent) 'arion-backups' }
$BackupDirectory = [System.IO.Path]::GetFullPath($BackupDirectory)
$projectPrefix = $ProjectRoot.TrimEnd('\') + '\'
if ($BackupDirectory.Equals($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $BackupDirectory.StartsWith($projectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'O diretório de backup deve ficar fora da pasta do projeto/web.'
}

$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$helper = Join-Path $ProjectRoot 'deploy\windows\backup_mysql.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $helper -PathType Leaf)) {
    throw 'Python da .venv ou helper de backup não encontrado.'
}
$mysqldump = Get-Command mysqldump.exe -ErrorAction SilentlyContinue
if (-not $mysqldump) { $mysqldump = Get-Command mysqldump -ErrorAction SilentlyContinue }
if (-not $mysqldump) { throw 'mysqldump não está no PATH desta conta Windows.' }

New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
$runRoot = Join-Path $ProjectRoot 'var\run'
$tempRoot = Join-Path $runRoot 'backup-private'
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$identitySid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$systemSid = 'S-1-5-18'
$adminsSid = 'S-1-5-32-544'
foreach ($directory in @($BackupDirectory, $tempRoot)) {
    & icacls.exe $directory '/inheritance:r' '/grant:r' `
        "*${identitySid}:(OI)(CI)M" "*${systemSid}:(OI)(CI)F" "*${adminsSid}:(OI)(CI)F" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível proteger a pasta de backup/temporários.' }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$output = Join-Path $BackupDirectory "arion-db-$stamp.sql"
if (Test-Path -LiteralPath $output) { throw 'Já existe backup com este timestamp; tente novamente.' }
$oldArionEnv = $env:ARION_ENV
try {
    $env:ARION_ENV = 'production'
    & $python $helper --mysqldump $mysqldump.Source --output $output --temp-dir $tempRoot
    if ($LASTEXITCODE -ne 0) { throw 'O dump MySQL não foi concluído.' }
} finally {
    if ($null -eq $oldArionEnv) { Remove-Item Env:ARION_ENV -ErrorAction SilentlyContinue } else { $env:ARION_ENV = $oldArionEnv }
}

if ($RetentionDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    Get-ChildItem -LiteralPath $BackupDirectory -File -Filter 'arion-db-*.sql' |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
}
Write-Output "Backup disponível fora da pasta web: $output"

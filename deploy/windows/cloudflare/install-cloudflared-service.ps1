param(
    [Parameter(Mandatory = $true)][guid]$TunnelId,
    [Parameter(Mandatory = $true)][string]$Hostname,
    [Parameter(Mandatory = $true)][string]$CredentialsFile,
    [string]$CloudflaredPath = 'C:\Cloudflared\bin\cloudflared.exe',
    [ValidateRange(1, 65535)][int]$LocalPort = 8000
)

$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este script em PowerShell elevado para instalar o serviço Windows.'
}
if (-not (Test-Path -LiteralPath $CloudflaredPath -PathType Leaf)) { throw 'cloudflared.exe não encontrado.' }
if (-not (Test-Path -LiteralPath $CredentialsFile -PathType Leaf)) { throw 'O JSON de credenciais do Tunnel não foi encontrado.' }
if ($Hostname -notmatch '^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$') {
    throw 'Informe um hostname DNS completo, sem wildcard ou esquema.'
}
if (Get-Service -Name 'Cloudflared' -ErrorAction SilentlyContinue) {
    throw 'O serviço Cloudflared já existe; nenhuma configuração foi sobrescrita.'
}

$systemCloudflareRoot = Join-Path $env:SystemRoot 'System32\config\systemprofile\.cloudflared'
$programDataRoot = Join-Path $env:ProgramData 'ARION'
$logRoot = Join-Path $programDataRoot 'logs'
New-Item -ItemType Directory -Force -Path $systemCloudflareRoot, $logRoot | Out-Null
$systemSid = 'S-1-5-18'
$adminsSid = 'S-1-5-32-544'
foreach ($directory in @($systemCloudflareRoot, $logRoot)) {
    & icacls.exe $directory '/inheritance:r' '/grant:r' `
        "*${systemSid}:(OI)(CI)F" "*${adminsSid}:(OI)(CI)F" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível restringir acesso aos arquivos do Tunnel/logs.' }
}

$credentialTarget = Join-Path $systemCloudflareRoot ($TunnelId.ToString() + '.json')
$configPath = Join-Path $systemCloudflareRoot 'config.yml'
$logPath = Join-Path $logRoot 'cloudflared.log'
if ((Test-Path -LiteralPath $credentialTarget -PathType Leaf) -or (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw 'Já existe configuração local do Cloudflared; nenhum arquivo foi sobrescrito.'
}
Copy-Item -LiteralPath $CredentialsFile -Destination $credentialTarget
$config = @"
tunnel: $TunnelId
credentials-file: '$credentialTarget'
no-autoupdate: true
loglevel: info
logfile: '$logPath'
ingress:
  - hostname: $Hostname
    service: http://127.0.0.1:$LocalPort
  - service: http_status:404
"@
Set-Content -LiteralPath $configPath -Value $config -Encoding utf8

& $CloudflaredPath "--config=$configPath" 'tunnel' 'ingress' 'validate' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'A configuração de ingress do Tunnel não passou na validação local.' }

$createdService = $false
try {
    & $CloudflaredPath 'service' 'install'
    if ($LASTEXITCODE -ne 0) { throw 'cloudflared não conseguiu registrar o serviço Windows.' }
    $createdService = $true
    $imagePath = '"{0}" --config="{1}" tunnel run' -f $CloudflaredPath, $configPath
    & sc.exe config Cloudflared "binPath= $imagePath" 'start= auto' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível configurar a linha de execução do serviço Cloudflared.' }
    & sc.exe failure Cloudflared 'reset= 86400' 'actions= restart/5000/restart/15000/restart/60000' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível configurar a recuperação automática do serviço Cloudflared.' }
    Start-Service -Name 'Cloudflared'
} catch {
    if ($createdService) { & sc.exe delete Cloudflared | Out-Null }
    throw
}

Write-Output 'Serviço Cloudflared instalado e iniciado. O DNS/hostname continua sob configuração manual da conta Cloudflare.'

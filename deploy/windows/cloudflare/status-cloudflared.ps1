$ErrorActionPreference = 'Stop'
$service = Get-Service -Name 'Cloudflared' -ErrorAction SilentlyContinue
if ($service) {
    Write-Output "Cloudflared: $($service.Status)"
    if ($service.Status -eq 'Running') { exit 0 }
    exit 1
}
Write-Output 'Cloudflared: Not installed'
exit 1

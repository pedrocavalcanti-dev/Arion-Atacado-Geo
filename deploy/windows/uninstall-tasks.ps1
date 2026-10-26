param([string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)

$ErrorActionPreference = 'Stop'
$confirmation = Read-Host 'Digite REMOVER TAREFAS ARION para confirmar a remoção das duas tarefas (dados e banco não serão apagados)'
if ($confirmation -cne 'REMOVER TAREFAS ARION') { throw 'Confirmação não corresponde; nenhuma tarefa foi removida.' }
foreach ($name in @('ARION-Web', 'ARION-Integration-Worker')) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
    }
}
Write-Output 'Tarefas removidas. Banco, backups e configuração local foram preservados.'

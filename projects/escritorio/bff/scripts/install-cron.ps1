$ps = "powershell.exe"
$dir = "C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff\scripts"

$bffTaskInstalled = $false
try {
  Register-ScheduledTask -TaskName "Aeternum BFF" -Force -ErrorAction Stop `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
    -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\start-bff.ps1`"") `
    -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)) | Out-Null
  $bffTaskInstalled = $true
} catch {
  # AtLogOn pode exigir administrador. O launcher da pasta Startup cobre o mesmo
  # boot sem elevar o processo inteiro nem esconder a falha.
  $startup = [Environment]::GetFolderPath("Startup")
  $launcher = Join-Path $startup "AeternumBFF.cmd"
  @"
@echo off
start "" /min powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "$dir\start-bff.ps1"
"@ | Set-Content -LiteralPath $launcher -Encoding Ascii
  Write-Warning "Task AtLogOn sem permissao; fallback Startup atualizado: $launcher"
}

# Os ritos do dia vêm de ritos.json, a fonte única (SPEC §4). sync-cron.ps1 registra
# e reconcilia as sete tarefas a partir dele.
& "$dir\sync-cron.ps1"

if ($bffTaskInstalled) {
  Start-ScheduledTask -TaskName "Aeternum BFF"
} elseif (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $ps -WindowStyle Hidden `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$dir\start-bff.ps1"
}

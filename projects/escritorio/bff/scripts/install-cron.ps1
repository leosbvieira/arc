$ps = "powershell.exe"
$dir = "C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff\scripts"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

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

# Os ritos do dia, na ORDEM em que acontecem (SPEC §4):
#   5h30  A1a  o toque      — "dia yoga ou dia corrida?" (POST /dia/template)
#   8h20  A1b  o check-in   — energia, clareza, prioridade nº1 (POST /abertura/checkin)
#   8h30       o jornal     — abre Capturar para a leitura de notícias
#   9h00       o digest     — as cobranças do dia
#  19h00  A2   o Shutdown   — fecha o trabalho, follow-ups, 3 prioridades de amanhã
#  21h00  A3   o fechamento — diário + rotinas
# dom 20h A4   a review semanal
Register-ScheduledTask -TaskName "Aeternum Toque" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 05:30) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind toque") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Check-in" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 08:20) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind checkin") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Jornal" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 08:30) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind jornal") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Digest" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 09:00) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\run-digest.ps1`"") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Shutdown" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 19:00) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind shutdown") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Fechamento" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 21:00) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind closing") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Review" -Force `
  -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 20:00) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind review") -Settings $settings

if ($bffTaskInstalled) {
  Start-ScheduledTask -TaskName "Aeternum BFF"
} elseif (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $ps -WindowStyle Hidden `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$dir\start-bff.ps1"
}
Get-ScheduledTask -TaskName "Aeternum *" | Format-Table TaskName, State

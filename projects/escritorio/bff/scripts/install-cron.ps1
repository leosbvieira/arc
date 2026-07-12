$ps = "powershell.exe"
$dir = "C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff\scripts"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName "Aeternum BFF" -Force `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\start-bff.ps1`"") `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1))

# Os ritos do dia, na ORDEM em que acontecem (SPEC §4):
#   5h30  A1a  o toque      — "dia yoga ou dia corrida?" (POST /dia/template)
#   8h20  A1b  o check-in   — energia, clareza, prioridade nº1 (POST /abertura/checkin)
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

Start-ScheduledTask -TaskName "Aeternum BFF"
Get-ScheduledTask -TaskName "Aeternum *" | Format-Table TaskName, State

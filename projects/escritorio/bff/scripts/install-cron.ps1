$ps = "powershell.exe"
$dir = "C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff\scripts"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName "Aeternum BFF" -Force `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\start-bff.ps1`"") `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1))

Register-ScheduledTask -TaskName "Aeternum Digest" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 09:00) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\run-digest.ps1`"") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Fechamento" -Force `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 21:00) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind closing") -Settings $settings

Register-ScheduledTask -TaskName "Aeternum Review" -Force `
  -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 20:00) `
  -Action (New-ScheduledTaskAction -Execute $ps -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\nudge.ps1`" -Kind review") -Settings $settings

Start-ScheduledTask -TaskName "Aeternum BFF"
Get-ScheduledTask -TaskName "Aeternum *" | Format-Table TaskName, State

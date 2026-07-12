param([ValidateSet("toque", "checkin", "shutdown", "closing", "review")][string]$Kind = "closing")
$bff = "http://127.0.0.1:8000"
$envFile = "C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff\.env"
$token = (Select-String -Path $envFile -Pattern '^INTERNAL_TOKEN=(.+)$').Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
$up = $false
for ($i = 0; $i -lt 6; $i++) {
    try { Invoke-RestMethod "$bff/health" -TimeoutSec 5 | Out-Null; $up = $true; break } catch { Start-Sleep 5 }
}
if (-not $up) {
    # recovery: tenta a task agendada; se nao existir (registro AtLogOn exige admin), sobe o script direto
    try { Start-ScheduledTask -TaskName "Aeternum BFF" -ErrorAction Stop } catch {
        Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File','C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff\scripts\start-bff.ps1' -WindowStyle Hidden
    }
    for ($i = 0; $i -lt 24; $i++) {
        try { Invoke-RestMethod "$bff/health" -TimeoutSec 5 | Out-Null; $up = $true; break } catch { Start-Sleep 10 }
    }
}
if ($up) {
    Invoke-RestMethod -Method Post "$bff/internal/nudge" -Headers @{ "X-Internal-Token" = $token } `
      -ContentType "application/json" -Body (@{ kind = $Kind } | ConvertTo-Json) -TimeoutSec 120
}

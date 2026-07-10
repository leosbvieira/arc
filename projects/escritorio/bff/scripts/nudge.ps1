param([ValidateSet("closing", "review")][string]$Kind = "closing")
$bff = "http://127.0.0.1:8000"
$envFile = "C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff\.env"
$token = (Select-String -Path $envFile -Pattern '^INTERNAL_TOKEN=(.+)$').Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
$up = $false
for ($i = 0; $i -lt 6; $i++) {
    try { Invoke-RestMethod "$bff/health" -TimeoutSec 5 | Out-Null; $up = $true; break } catch { Start-Sleep 5 }
}
if (-not $up) {
    Start-ScheduledTask -TaskName "Aeternum BFF"
    for ($i = 0; $i -lt 24; $i++) {
        try { Invoke-RestMethod "$bff/health" -TimeoutSec 5 | Out-Null; $up = $true; break } catch { Start-Sleep 10 }
    }
}
if ($up) {
    Invoke-RestMethod -Method Post "$bff/internal/nudge" -Headers @{ "X-Internal-Token" = $token } `
      -ContentType "application/json" -Body (@{ kind = $Kind } | ConvertTo-Json) -TimeoutSec 120
}

Set-Location "C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff"

$Listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($Listeners) {
    $ProcessIds = $Listeners | Select-Object -ExpandProperty OwningProcess -Unique
    Write-Host "Porta 8000 já está ocupada pelo(s) PID(s): $($ProcessIds -join ', ')"
    exit 1
}

# A agenda converge no boot: mudar ritos.json e reiniciar basta. Fail-open lá dentro.
try { & "$PSScriptRoot\sync-cron.ps1" } catch { Write-Warning "sync-cron falhou: $_" }

& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

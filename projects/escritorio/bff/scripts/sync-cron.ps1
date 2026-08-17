<#
  Gera E reconcilia as tarefas do Agendador a partir de ritos.json, a fonte única.

  Antes disto os `-At` eram literais aqui e no texto do push. Renomear ou remover um
  rito deixava a tarefa antiga instalada, disparando em paralelo com a nova.

  -DryRun devolve o plano em JSON e NÃO toca no Agendador. É assim que o teste roda.
#>
param(
  [switch]$DryRun,
  [string]$Arquivo = "",
  [string]$TarefasInstaladas = $null   # só no -DryRun: lista separada por vírgula
)

$ErrorActionPreference = "Stop"

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Arquivo) { $Arquivo = Join-Path (Split-Path -Parent $dir) "ritos.json" }

# Fail-closed: JSON quebrado aborta. Agenda pela metade é pior que agenda velha.
$ritos = Get-Content -LiteralPath $Arquivo -Raw -Encoding UTF8 | ConvertFrom-Json
if ($ritos -isnot [array] -or $ritos.Count -eq 0) { throw "ritos.json vazio ou não é lista" }

$DIAS_EN = @{ "segunda" = "Monday"; "terça" = "Tuesday"; "quarta" = "Wednesday";
              "quinta" = "Thursday"; "sexta" = "Friday"; "sábado" = "Saturday";
              "domingo" = "Sunday" }

$registrar = @()
foreach ($r in $ritos) {
  $script = if ($r.script -eq "digest") { "run-digest.ps1" } else { "nudge.ps1" }
  $trigger = if ($null -eq $r.dia) { "Daily $($r.hora)" } else { "Weekly $($DIAS_EN[$r.dia]) $($r.hora)" }
  $registrar += [ordered]@{ task = $r.task; slug = $r.slug; trigger = $trigger; script = $script }
}

$desejadas = $registrar | ForEach-Object { $_.task }
if ($PSBoundParameters.ContainsKey("TarefasInstaladas")) {
  $instaladas = @($TarefasInstaladas -split "," | Where-Object { $_ })
} else {
  $instaladas = @(Get-ScheduledTask -TaskName "Aeternum *" -ErrorAction SilentlyContinue |
                  ForEach-Object { $_.TaskName })
}
# "Aeternum BFF" não vem do JSON (dispara no logon) e nunca é removida.
$remover = @($instaladas | Where-Object { $_ -ne "Aeternum BFF" -and $desejadas -notcontains $_ })

if ($DryRun) {
  [ordered]@{ registrar = $registrar; remover = $remover } | ConvertTo-Json -Depth 4 -Compress
  exit 0
}

$ps = "powershell.exe"
# SEM -StartWhenAvailable, de proposito. Com ele, o Windows executa TODO gatilho
# perdido no proximo boot -- e como sao seis ritos diarios, o PC ligado as 22h44
# disparava os seis no mesmo segundo, incluindo o toque das 5h30. Isso aconteceu
# em sete dias diferentes (notif_log tem a rajada de 0 segundo), e e o que ensina
# a ignorar o canal.
#
# A "Aeternum BFF" (install-cron.ps1) MANTEM a flag: ali o comportamento e o
# desejado -- se o logon foi perdido, subir o servidor assim que der esta certo.
# Um servidor atrasado ainda serve; um aviso atrasado, nao.
#
# A guarda de verdade e do lado do servidor (`ritos.atrasado`), porque o
# systemd do VPS tem `Persistent=true`, que se comporta igual a esta flag.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Fail-OPEN daqui pra baixo: erro do Agendador (permissão, política) não pode
# impedir o BFF de subir -- mas grita, porque a agenda fica divergente.
foreach ($p in $registrar) {
  try {
    $r = $ritos | Where-Object { $_.slug -eq $p.slug }
    $trigger = if ($null -eq $r.dia) {
      New-ScheduledTaskTrigger -Daily -At $r.hora
    } else {
      New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DIAS_EN[$r.dia] -At $r.hora
    }
    $arg = "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$dir\$($p.script)`""
    if ($p.script -eq "nudge.ps1") { $arg += " -Kind $($p.slug)" }
    Register-ScheduledTask -TaskName $p.task -Force -Trigger $trigger `
      -Action (New-ScheduledTaskAction -Execute $ps -Argument $arg) -Settings $settings | Out-Null
  } catch {
    Write-Warning "AGENDA DIVERGENTE: falhou registrar '$($p.task)' ($($p.trigger)): $_"
  }
}
foreach ($t in $remover) {
  try { Unregister-ScheduledTask -TaskName $t -Confirm:$false }
  catch { Write-Warning "AGENDA DIVERGENTE: falhou remover '$t': $_" }
}

# Esperado x instalado, lado a lado: divergência visível numa olhada.
Write-Host "`nRitos (esperado x instalado):"
foreach ($p in $registrar) {
  $viva = Get-ScheduledTask -TaskName $p.task -ErrorAction SilentlyContinue
  $estado = if ($viva) { $viva.State } else { "AUSENTE" }
  "{0,-22} {1,-24} {2}" -f $p.task, $p.trigger, $estado | Write-Host
}

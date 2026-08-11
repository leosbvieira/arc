# Fatia 1A — Fonte única de tarifas e horários · Plano de implementação

> **Para workers agênticos:** SUB-SKILL OBRIGATÓRIA: use `superpowers:subagent-driven-development`
> (recomendado) ou `superpowers:executing-plans` para executar tarefa a tarefa. Os passos usam
> checkbox (`- [ ]`).

**Objetivo:** fazer as tarifas de pontos e os horários dos ritos terem **uma** fonte, consumida pelo
Agendador do Windows, pelo texto do push, pelo BFF e por todas as telas do app — hoje estão copiados em
cinco lugares que só coincidem por manutenção manual.

**Arquitetura:** um `bff/ritos.json` lido por Python e por PowerShell é a fonte dos horários; o
`config.py` continua sendo a fonte das tarifas; uma rota nova `GET /wiki/parametros` projeta as duas e
o schema JSON dela — normalizado — vira o contrato e o validador em runtime do app. No app, um
`ParametrosProvider` é o único dono de buscar, validar, cachear e revalidar, e os módulos puros
(`mesaView`, `homeAction`) passam a receber os horários por parâmetro, como já recebem a tabela de
pontos.

**Stack:** FastAPI + Pydantic v2 + pytest (BFF) · React Native/Expo + TypeScript + `node:test` em
`.mjs` (app) · PowerShell 5.1 (Agendador do Windows).

**Spec:** `WIKI-SPEC.md` v6. Este plano cobre **só a 1A** (§12). A 1B (a tela "Como funciona") tem plano
próprio e depende desta.

## Restrições globais

Valem para toda tarefa, sem repetição:

- **Nenhum literal de tarifa ou horário sobrevive** fora de `config.py` e `ritos.json`. Se você
  escreveu `20`, `19:00` ou `"19h"` em qualquer outro arquivo, a tarefa está errada.
- **O slug do rito das 21h é `closing`.** Não renomeie para `fechamento`. É o vocabulário do BFF
  (`/closing/routines`, `/closing/draft`, `/closing/approve`, evento `closing_approved`, kind
  `nudge_closing`, `Literal` em `main.py:483`). Ver `WIKI-SPEC.md` §3.2.
- **Módulo puro do app não tem import de valor.** `mesaView.ts` e `closingPoints.ts` importam só
  `type` — o Node tira os tipos sozinho, mas não resolve import relativo em runtime nos testes `.mjs`.
  Siga isso em `parametrosCore.ts`.
- **Testes do app:** `cd app && npm test` (`node --test tests/*.test.mjs`). Typecheck:
  `npm run typecheck`. Os dois juntos: `npm run check`.
- **Testes do BFF:** `cd bff && python -m pytest -q`. O `conftest.py` já aponta o `db_path` para um
  temporário de sessão e já sobrescreve os segredos default — **não** mexa nisso.
- **Nunca suba o BFF com o `.env` real durante teste.** Ele lê o PAT do Leo e o worker grava no vault
  de verdade. Os testes usam `TestClient` com `app.dependency_overrides[require_auth]`.
- **Uma tarefa, um commit.** Mensagem em português, imperativo ou fato, sem `Co-Authored-By` inventado.

## Mapa de arquivos

| Arquivo | Responsabilidade | Tarefa |
|---|---|---|
| `bff/ritos.json` | **A** fonte dos horários. Dado, sem lógica | 1 |
| `bff/app/ritos.py` | Carrega, valida no import, e formata (`hora_curta`) | 1 |
| `bff/app/main.py` | `NUDGE_COPY` interpolado; rota `GET /wiki/parametros` | 2, 4 |
| `bff/app/wiki_schema.py` | Normaliza o JSON Schema do Pydantic para o dialeto plano | 4 |
| `bff/scripts/sync-cron.ps1` | Gera E reconcilia as tarefas do Agendador a partir do JSON | 3 |
| `bff/scripts/install-cron.ps1` · `start-bff.ps1` | Passam a chamar o sync | 3 |
| `app/src/wiki-schema.json` | O contrato, no bundle. **Arquivo único** | 4 |
| `app/src/parametrosCore.ts` | Tipos, `DEFAULT_PARAMS`, `validar`, `decidir`, `aplicar`, `minutos`, `fonteParaWiki` | 5 |
| `app/src/parametros.tsx` | O provider: único dono de fetch, cache e revalidação | 6 |
| `app/src/api.ts` | `getParametros()` | 6 |
| `app/src/mesaView.ts` · `homeAction.ts` | Recebem `ritos` por parâmetro | 7 |
| `app/src/screens/{Capture,Fechar,Tasks}.tsx` | 7 call sites de `POINTS.` passam pelo provider | 8 |
| `app/src/theme.ts` | `POINTS` é **apagado** — a semente única passa a ser `DEFAULT_PARAMS` | 8 |

---

## Tarefa 1 — `ritos.json` e `ritos.py`

**Arquivos:**
- Criar: `bff/ritos.json`
- Criar: `bff/app/ritos.py`
- Testar: `bff/tests/test_ritos.py`

**Interfaces:**
- Consome: nada.
- Produz: `ritos.RITOS: list[dict]`, `ritos.hora(slug) -> str` (`"19:00"`),
  `ritos.hora_curta(slug) -> str` (`"19h"`, `"5h30"`), `ritos.slugs_por_script(script) -> list[str]`.
  As tarefas 2, 3 e 4 dependem desses nomes.

- [ ] **Passo 1: criar o `bff/ritos.json`**

Os valores vêm do `install-cron.ps1` atual, verbatim. Ordem: diários em ordem cronológica, semanais
depois.

```json
[
  { "slug": "toque",    "hora": "05:30", "dia": null,      "task": "Aeternum Toque",      "script": "nudge"  },
  { "slug": "checkin",  "hora": "08:20", "dia": null,      "task": "Aeternum Check-in",   "script": "nudge"  },
  { "slug": "jornal",   "hora": "08:30", "dia": null,      "task": "Aeternum Jornal",     "script": "nudge"  },
  { "slug": "digest",   "hora": "09:00", "dia": null,      "task": "Aeternum Digest",     "script": "digest" },
  { "slug": "shutdown", "hora": "19:00", "dia": null,      "task": "Aeternum Shutdown",   "script": "nudge"  },
  { "slug": "closing",  "hora": "21:00", "dia": null,      "task": "Aeternum Fechamento", "script": "nudge"  },
  { "slug": "review",   "hora": "20:00", "dia": "domingo", "task": "Aeternum Review",     "script": "nudge"  }
]
```

- [ ] **Passo 2: escrever o teste que falha**

`bff/tests/test_ritos.py`:

```python
"""A fonte única dos ritos. Antes disto, os horários viviam em cinco lugares."""
import json

import pytest

from app import ritos


def test_carrega_os_sete_ritos():
    assert [r["slug"] for r in ritos.RITOS] == [
        "toque", "checkin", "jornal", "digest", "shutdown", "closing", "review",
    ]


def test_hora_e_hora_curta():
    assert ritos.hora("shutdown") == "19:00"
    assert ritos.hora_curta("shutdown") == "19h"
    assert ritos.hora_curta("toque") == "5h30"
    assert ritos.hora_curta("checkin") == "8h20"


def test_slug_desconhecido_levanta():
    with pytest.raises(KeyError):
        ritos.hora("nao-existe")


def test_slugs_por_script():
    assert ritos.slugs_por_script("digest") == ["digest"]
    assert "closing" in ritos.slugs_por_script("nudge")
    assert "digest" not in ritos.slugs_por_script("nudge")


@pytest.mark.parametrize("quebra", [
    [{"slug": "a", "hora": "05:30", "dia": None, "task": "T A", "script": "nudge"},
     {"slug": "a", "hora": "06:30", "dia": None, "task": "T B", "script": "nudge"}],   # slug duplicado
    [{"slug": "a", "hora": "05:30", "dia": None, "task": "T", "script": "nudge"},
     {"slug": "b", "hora": "06:30", "dia": None, "task": "T", "script": "nudge"}],     # task duplicada
    [{"slug": "a", "hora": "5:30",  "dia": None, "task": "T", "script": "nudge"}],     # hora sem zero
    [{"slug": "a", "hora": "25:00", "dia": None, "task": "T", "script": "nudge"}],     # hora inválida
    [{"slug": "a", "hora": "05:30", "dia": "lunes", "task": "T", "script": "nudge"}],  # dia inválido
    [{"slug": "a", "hora": "05:30", "dia": None, "task": "T", "script": "cron"}],      # script inválido
    [{"slug": "a", "hora": "02:59", "dia": "domingo", "task": "T", "script": "nudge"}],  # semanal < 03:00
])
def test_validacao_rejeita(quebra):
    with pytest.raises(ValueError):
        ritos.validar(quebra)


def test_semanal_a_partir_das_tres_e_aceito():
    ritos.validar([{"slug": "a", "hora": "03:00", "dia": "domingo", "task": "T", "script": "nudge"}])
```

O caso `02:59` protege o `review − 3h` do `homeAction` (tarefa 7): review de madrugada produziria
limiar negativo ou teria que virar para o sábado, e o código não faz rollover de dia da semana.
Ver `WIKI-SPEC.md` §3.3.

- [ ] **Passo 3: rodar e ver falhar**

Rodar: `cd bff && python -m pytest tests/test_ritos.py -q`
Esperado: FAIL com `ModuleNotFoundError: No module named 'app.ritos'`.

- [ ] **Passo 4: implementar `bff/app/ritos.py`**

```python
"""Fonte única dos horários dos ritos.

Antes deste módulo os horários viviam em CINCO lugares e nenhum era autoritativo:
o gatilho do Agendador (`install-cron.ps1`), o texto do push (`NUDGE_COPY`), e as
telas (`mesaView.ts`, `homeAction.ts`). Mudar o Shutdown para 18:00 fazia o
Agendador disparar às 18h enquanto o push e a Mesa continuavam dizendo 19h.

O arquivo é JSON, e não um campo do `config.py`, por um motivo só: o
`sync-cron.ps1` precisa lê-lo, e `ConvertFrom-Json` é nativo do PowerShell.
Acoplar o instalador do cron ao venv quebraria no dia de reconstruir o ambiente.
"""
import json
import re
from pathlib import Path

_ARQUIVO = Path(__file__).resolve().parent.parent / "ritos.json"

DIAS = {"segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"}
SCRIPTS = {"nudge", "digest"}
_HORA = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Rito semanal antes disto quebraria `review - 3h` no homeAction, que não faz
# rollover de dia da semana. Restrição explícita vale mais que rollover que
# ninguém exercita (WIKI-SPEC §3.3).
_MIN_SEMANAL = 3 * 60


def minutos(hora: str) -> int:
    """'18:30' -> 1110."""
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def validar(dados: list[dict]) -> list[dict]:
    slugs, tasks = set(), set()
    for r in dados:
        slug = r.get("slug")
        if not slug or slug in slugs:
            raise ValueError(f"slug ausente ou duplicado: {slug!r}")
        slugs.add(slug)

        task = r.get("task")
        if not task or task in tasks:
            # Duas tarefas com o mesmo nome: o segundo Register-ScheduledTask
            # -Force sobrescreveria o primeiro em silêncio.
            raise ValueError(f"task ausente ou duplicada: {task!r}")
        tasks.add(task)

        hora = r.get("hora", "")
        if not _HORA.match(hora):
            raise ValueError(f"hora inválida em {slug!r}: {hora!r}")

        dia = r.get("dia")
        if dia is not None and dia not in DIAS:
            raise ValueError(f"dia inválido em {slug!r}: {dia!r}")
        if dia is not None and minutos(hora) < _MIN_SEMANAL:
            raise ValueError(f"rito semanal antes das 03:00 em {slug!r}: {hora!r}")

        if r.get("script") not in SCRIPTS:
            raise ValueError(f"script inválido em {slug!r}: {r.get('script')!r}")
    return dados


def _carregar() -> list[dict]:
    return validar(json.loads(_ARQUIVO.read_text(encoding="utf-8")))


RITOS = _carregar()
_POR_SLUG = {r["slug"]: r for r in RITOS}


def rito(slug: str) -> dict:
    return _POR_SLUG[slug]


def hora(slug: str) -> str:
    return _POR_SLUG[slug]["hora"]


def hora_curta(slug: str) -> str:
    """'19:00' -> '19h'; '05:30' -> '5h30'. O formato que o Leo já lê nos nudges."""
    h, m = _POR_SLUG[slug]["hora"].split(":")
    return f"{int(h)}h" if m == "00" else f"{int(h)}h{m}"


def slugs_por_script(script: str) -> list[str]:
    return [r["slug"] for r in RITOS if r["script"] == script]
```

- [ ] **Passo 5: rodar e ver passar**

Rodar: `cd bff && python -m pytest tests/test_ritos.py -q`
Esperado: PASS, 11 testes.

- [ ] **Passo 6: commitar**

```bash
git add bff/ritos.json bff/app/ritos.py bff/tests/test_ritos.py
git commit -m "feat(escritorio): os horarios dos ritos ganham uma fonte unica"
```

---

## Tarefa 2 — `NUDGE_COPY` para de escrever a hora à mão

**Arquivos:**
- Modificar: `bff/app/main.py:41-48`
- Testar: `bff/tests/test_ritos.py` (acrescenta)

**Interfaces:**
- Consome: `ritos.hora_curta` (tarefa 1).
- Produz: `main.PRIORIDADES_SHUTDOWN: int`, `main.NUDGE_TEMPLATE: dict[str, str]`,
  `main.montar_nudge_copy(hora_curta) -> dict[str, str]`, `main.NUDGE_COPY` (igual ao de hoje em valor).
  A tarefa 4 consome `PRIORIDADES_SHUTDOWN`.

**Por que separar template de texto renderizado:** o teste precisa provar duas coisas diferentes — que
o **template** não tem hora escrita à mão, e que o **renderizado** mostra a hora do próprio slug. Se
`NUDGE_COPY` fosse construído inline, o teste da primeira leria uma string que já contém `"19h"` e não
teria como distinguir hora interpolada de hora digitada.

- [ ] **Passo 1: escrever o teste que falha**

Acrescente em `bff/tests/test_ritos.py`:

```python
import re

from app import main

_HORA_NO_TEXTO = re.compile(r"\b\d{1,2}h(\d{2})?\b")


def test_template_do_nudge_nao_tem_hora_escrita_a_mao():
    for slug, texto in main.NUDGE_TEMPLATE.items():
        assert not _HORA_NO_TEXTO.search(texto), f"{slug} tem hora no template: {texto!r}"


def test_cada_nudge_mostra_a_hora_do_proprio_slug():
    """Sentinela distinta por slug: pega o copy que interpola a hora do rito errado."""
    sentinelas = {r["slug"]: f"{i + 1}h{i + 1:02d}" for i, r in enumerate(ritos.RITOS)}
    copy = main.montar_nudge_copy(lambda slug: sentinelas[slug])
    for slug, texto in copy.items():
        assert sentinelas[slug] in texto, f"{slug} não mostra a própria hora: {texto!r}"
        for outro, s in sentinelas.items():
            if outro != slug:
                assert s not in texto, f"{slug} mostra a hora de {outro}"


def test_chaves_do_nudge_copy_sao_exatamente_os_slugs_nudge():
    assert set(main.NUDGE_COPY) == set(ritos.slugs_por_script("nudge"))


def test_validateset_do_nudge_ps1_bate_com_os_slugs():
    """O ValidateSet é a primeira linha do script: slug fora dele mata o rito
    antes de qualquer chamada HTTP."""
    from pathlib import Path
    fonte = (Path(__file__).resolve().parent.parent / "scripts" / "nudge.ps1").read_text(encoding="utf-8")
    membros = set(re.findall(r'"([a-z]+)"', fonte.splitlines()[0]))
    assert membros == set(ritos.slugs_por_script("nudge"))
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `cd bff && python -m pytest tests/test_ritos.py -q`
Esperado: FAIL com `AttributeError: module 'app.main' has no attribute 'NUDGE_TEMPLATE'`.

- [ ] **Passo 3: implementar**

Substitua `bff/app/main.py:40-48` por:

```python
# Tom: seco e factual (lei 4 — o sistema não motiva, não envergonha; diz o fato e o custo).
# A HORA NÃO SE ESCREVE AQUI: ela vem de `ritos.json`, a fonte única. Antes disto o
# texto dizia "19h" enquanto o Agendador podia disparar em outra hora.
PRIORIDADES_SHUTDOWN = 3

NUDGE_TEMPLATE = {
    "toque": "{hora} — dia yoga ou dia corrida?",
    "checkin": "{hora} — check-in: energia, clareza, prioridade nº1. 60 segundos.",
    "jornal": "{hora} — jornal de leitura de notícias. Abra Capturar para iniciar.",
    "shutdown": "{hora} — Shutdown: fechar o trabalho, follow-ups, {prioridades} prioridades de amanhã.",
    "closing": "{hora} — fechar o dia? 90 segundos bastam: 1 linha + checks.",
    "review": "domingo {hora} — review semanal. Os números da semana te esperam no app.",
}


def montar_nudge_copy(hora_curta=ritos.hora_curta) -> dict[str, str]:
    return {
        slug: t.format(hora=hora_curta(slug), prioridades=PRIORIDADES_SHUTDOWN)
        for slug, t in NUDGE_TEMPLATE.items()
    }


NUDGE_COPY = montar_nudge_copy()
```

E acrescente `ritos` ao import de `app` no topo do arquivo (junto de `store`, `tz` etc.).

- [ ] **Passo 4: rodar e ver passar**

Rodar: `cd bff && python -m pytest tests/test_ritos.py -q`
Esperado: PASS, 15 testes.

- [ ] **Passo 5: provar que o texto não mudou**

Rodar: `cd bff && python -c "from app.main import NUDGE_COPY; [print(f'{k}: {v}') for k,v in NUDGE_COPY.items()]"`

Esperado, **byte a byte igual ao de antes**:

```
toque: 5h30 — dia yoga ou dia corrida?
checkin: 8h20 — check-in: energia, clareza, prioridade nº1. 60 segundos.
jornal: 8h30 — jornal de leitura de notícias. Abra Capturar para iniciar.
shutdown: 19h — Shutdown: fechar o trabalho, follow-ups, 3 prioridades de amanhã.
closing: 21h — fechar o dia? 90 segundos bastam: 1 linha + checks.
review: domingo 20h — review semanal. Os números da semana te esperam no app.
```

Diferente disso, o `hora_curta` está errado. Não siga em frente.

- [ ] **Passo 6: rodar a suíte inteira**

Rodar: `cd bff && python -m pytest -q`
Esperado: PASS. Se algum teste de notificação quebrou, ele dependia do texto literal — conserte o
teste para usar `main.NUDGE_COPY[slug]`, não o texto digitado.

- [ ] **Passo 7: commitar**

```bash
git add bff/app/main.py bff/tests/test_ritos.py
git commit -m "fix(escritorio): o push anunciava a hora que ele mesmo nao sabia"
```

---

## Tarefa 3 — `sync-cron.ps1`: gerar e reconciliar

**Arquivos:**
- Criar: `bff/scripts/sync-cron.ps1`
- Modificar: `bff/scripts/install-cron.ps1` (remove os sete `Register-ScheduledTask` literais)
- Modificar: `bff/scripts/start-bff.ps1` (chama o sync no boot)
- Testar: `bff/tests/test_sync_cron.py`

**Interfaces:**
- Consome: `bff/ritos.json` (tarefa 1).
- Produz: `sync-cron.ps1 -DryRun` imprime **JSON** na stdout com
  `{ registrar: [{task, slug, trigger, script}], remover: [task] }`. O teste depende desse formato.

**Por que `-DryRun` devolve JSON:** é a única forma de testar o consumidor PowerShell sem mexer no
Agendador da máquina do Leo. Sem isso, caminho errado do JSON, tradução errada de `domingo` ou escolha
errada entre `nudge.ps1` e `run-digest.ps1` passariam com toda a suíte verde.

- [ ] **Passo 1: escrever o teste que falha**

`bff/tests/test_sync_cron.py`:

```python
"""O consumidor PowerShell da fonte única, testado pelo plano que ele produz."""
import json
import subprocess
from pathlib import Path

import pytest

from app import ritos

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync-cron.ps1"


def plano(instaladas: list[str]) -> dict:
    saida = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(_SCRIPT), "-DryRun", "-TarefasInstaladas", ",".join(instaladas)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


def test_registra_um_por_rito_com_o_gatilho_certo():
    p = plano([])
    por_slug = {r["slug"]: r for r in p["registrar"]}
    assert set(por_slug) == {r["slug"] for r in ritos.RITOS}
    assert por_slug["shutdown"]["trigger"] == "Daily 19:00"
    assert por_slug["review"]["trigger"] == "Weekly Sunday 20:00"
    assert por_slug["shutdown"]["script"] == "nudge.ps1"
    assert por_slug["digest"]["script"] == "run-digest.ps1"
    assert por_slug["closing"]["task"] == "Aeternum Fechamento"


def test_remove_tarefa_obsoleta_e_preserva_o_bff():
    p = plano(["Aeternum Toque", "Aeternum Antigo", "Aeternum BFF"])
    assert p["remover"] == ["Aeternum Antigo"]


def test_nao_remove_nada_quando_o_instalado_bate():
    p = plano([r["task"] for r in ritos.RITOS] + ["Aeternum BFF"])
    assert p["remover"] == []


def test_json_invalido_aborta(tmp_path, monkeypatch):
    """Fail-closed: JSON quebrado não pode virar agenda pela metade."""
    ruim = tmp_path / "ritos.json"
    ruim.write_text("{ nao e lista", encoding="utf-8")
    saida = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(_SCRIPT), "-DryRun", "-Arquivo", str(ruim)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert saida.returncode != 0
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `cd bff && python -m pytest tests/test_sync_cron.py -q`
Esperado: FAIL — o script não existe.

- [ ] **Passo 3: implementar `bff/scripts/sync-cron.ps1`**

```powershell
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
if ($null -ne $TarefasInstaladas) {
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
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
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
```

- [ ] **Passo 4: rodar e ver passar**

Rodar: `cd bff && python -m pytest tests/test_sync_cron.py -q`
Esperado: PASS, 4 testes.

- [ ] **Passo 5: ligar o sync no instalador e no boot**

Em `bff/scripts/install-cron.ps1`, apague os **sete** blocos `Register-ScheduledTask` dos ritos
(linhas 709–743, do comentário `# Os ritos do dia...` até o bloco `Aeternum Review`) e o
`Get-ScheduledTask ... | Format-Table` do fim. Deixe o bloco `Aeternum BFF` e o fallback da pasta
Startup como estão. No lugar dos sete, uma linha:

```powershell
& "$dir\sync-cron.ps1"
```

Em `bff/scripts/start-bff.ps1`, antes de subir o uvicorn, acrescente:

```powershell
# A agenda converge no boot: mudar ritos.json e reiniciar basta. Fail-open lá dentro.
try { & "$PSScriptRoot\sync-cron.ps1" } catch { Write-Warning "sync-cron falhou: $_" }
```

- [ ] **Passo 6: verificar de verdade, na máquina**

Rodar: `powershell -NoProfile -ExecutionPolicy Bypass -File bff\scripts\sync-cron.ps1`
Esperado: a tabela esperado × instalado com as 7 tarefas em `Ready`, e nenhum `AGENDA DIVERGENTE`.

Depois: `Get-ScheduledTask -TaskName "Aeternum Fechamento" | Select-Object -Expand Triggers`
Esperado: `StartBoundary` às 21:00, diário.

- [ ] **Passo 7: commitar**

```bash
git add bff/scripts/sync-cron.ps1 bff/scripts/install-cron.ps1 bff/scripts/start-bff.ps1 bff/tests/test_sync_cron.py
git commit -m "feat(escritorio): a agenda do Windows passa a ser gerada, e reconciliada"
```

---

## Tarefa 4 — `GET /wiki/parametros` e o schema normalizado

**Arquivos:**
- Criar: `bff/app/wiki_schema.py`
- Criar: `app/src/wiki-schema.json`
- Modificar: `bff/app/main.py` (modelo + rota)
- Modificar: `bff/app/pontos.py` (expõe a constante da janela)
- Testar: `bff/tests/test_wiki_parametros.py`

**Interfaces:**
- Consome: `ritos.RITOS`, `main.PRIORIDADES_SHUTDOWN` (tarefas 1–2).
- Produz: `GET /wiki/parametros` com o corpo de `WIKI-SPEC.md` §3.1, e o arquivo
  `app/src/wiki-schema.json`. As tarefas 5 e 6 dependem dos dois.

**Por que normalizar:** o `model_json_schema()` do Pydantic v2 emite `$defs`/`$ref` para submodelos e
`anyOf: [{type:"string"},{type:"null"}]` para `dia: str | None`. O caminhador do app (tarefa 5)
implementa só o dialeto plano. Sem a normalização, regenerar o contrato quebraria o próprio teste,
sempre — foi o erro que a rodada 5 pegou.

- [ ] **Passo 1: escrever o teste que falha**

`bff/tests/test_wiki_parametros.py`:

```python
"""A rota que a wiki lê -- e que o app inteiro passa a ler junto."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ritos, store
from app.config import settings
from app.main import app, require_auth

_SCHEMA_APP = Path(__file__).resolve().parents[2] / "app" / "src" / "wiki-schema.json"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_exige_autenticacao():
    # Sem `with`: o lifespan sobe o worker de captura, e um teste de 401 não
    # tem por que ligar processo de fundo nenhum.
    assert TestClient(app).get("/wiki/parametros").status_code == 401


def test_devolve_os_parametros(client):
    p = client.get("/wiki/parametros").json()
    assert p["tarifas"]["rotina"] == settings.pontos_por_rotina
    assert p["punicao"]["limiar_furos"] == settings.routine_miss_threshold
    assert p["punicao"]["janela"] == "semana_iso"
    assert p["niveis"]["limiares"] == settings.nivel_limiares
    assert p["ciclo"]["semanas"] == settings.ciclo_semanas
    assert p["staging"]["dias_para_alerta"] == settings.staging_age_days
    assert p["shutdown"]["prioridades"] == 3
    assert len(p["areas"]) == 10
    assert [r["slug"] for r in p["ritos"]] == [r["slug"] for r in ritos.RITOS]
    assert p["ritos"][0]["hora"] == ritos.hora(p["ritos"][0]["slug"])


def test_valor_vem_do_settings_nao_de_literal(client, monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_rotina", 999)
    assert client.get("/wiki/parametros").json()["tarifas"]["rotina"] == 999


def test_schema_commitado_bate_com_o_modelo():
    from app.wiki_schema import schema_normalizado
    atual = schema_normalizado()
    commitado = json.loads(_SCHEMA_APP.read_text(encoding="utf-8"))
    assert atual == commitado, "regenere: python -m app.wiki_schema > ../app/src/wiki-schema.json"


def test_normalizacao_nao_deixa_dialeto_do_pydantic():
    from app.wiki_schema import schema_normalizado
    bruto = json.dumps(schema_normalizado())
    for proibido in ("$defs", "$ref", "anyOf", "const", "title", "description"):
        assert proibido not in bruto, f"normalização deixou {proibido}"


def test_so_usa_o_subconjunto_do_caminhador():
    from app.wiki_schema import PALAVRAS, schema_normalizado

    def anda(no):
        assert set(no) <= PALAVRAS, f"palavra fora do subconjunto: {set(no) - PALAVRAS}"
        for filho in no.get("properties", {}).values():
            anda(filho)
        if "items" in no:
            anda(no["items"])

    anda(schema_normalizado())
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `cd bff && python -m pytest tests/test_wiki_parametros.py -q`
Esperado: FAIL — a rota não existe (404) e `app.wiki_schema` não existe.

- [ ] **Passo 3: expor a constante da janela em `pontos.py`**

A janela do padrão é a semana ISO por decisão documentada no docstring do módulo, e não é
configurável. Acrescente logo depois dos imports de `bff/app/pontos.py`:

```python
# A janela do padrão, como rótulo para quem precisa EXIBIR a regra (a wiki).
# É a semana ISO por decisão de design -- ver o docstring acima.
JANELA = "semana_iso"
```

- [ ] **Passo 4: implementar `bff/app/wiki_schema.py`**

```python
"""Normaliza o JSON Schema do Pydantic para o dialeto plano que o app valida.

O `model_json_schema()` v2 emite `$defs`/`$ref` para submodelos e
`anyOf: [X, {type: "null"}]` para opcionais. O caminhador do app implementa só
`type`, `properties`, `required`, `items`, `minItems`, `enum` e `nullable`.
Sem esta etapa, regenerar o contrato quebraria o próprio teste, sempre.
"""
import json

PALAVRAS = {"type", "properties", "required", "items", "minItems", "enum", "nullable"}


def _normalizar(no: dict, defs: dict) -> dict:
    if "$ref" in no:
        nome = no["$ref"].rsplit("/", 1)[-1]
        return _normalizar(dict(defs[nome]), defs)

    if "anyOf" in no:
        ramos = [r for r in no["anyOf"] if r.get("type") != "null"]
        anulavel = len(ramos) != len(no["anyOf"])
        if len(ramos) != 1:
            raise ValueError(f"anyOf com {len(ramos)} ramos não-nulos: {no['anyOf']}")
        saida = _normalizar(dict(ramos[0]), defs)
        if anulavel:
            saida["nullable"] = True
        return saida

    saida = {}
    for chave, valor in no.items():
        if chave in ("title", "description", "default"):
            continue
        if chave == "const":
            saida["enum"] = [valor]
        elif chave == "properties":
            saida["properties"] = {k: _normalizar(dict(v), defs) for k, v in valor.items()}
        elif chave == "items":
            saida["items"] = _normalizar(dict(valor), defs)
        else:
            saida[chave] = valor
    return saida


def schema_normalizado() -> dict:
    from .main import ParametrosOut

    bruto = ParametrosOut.model_json_schema()
    defs = bruto.pop("$defs", {})
    return _normalizar(bruto, defs)


if __name__ == "__main__":
    print(json.dumps(schema_normalizado(), indent=2, ensure_ascii=False, sort_keys=True))
```

- [ ] **Passo 5: implementar o modelo e a rota em `main.py`**

Perto dos outros modelos de saída:

```python
class RitoOut(BaseModel):
    slug: str
    hora: str
    # Sem `= None`: o campo é obrigatório porém anulável. Com default, o
    # `model_json_schema()` emitiria `default: null`, fora do dialeto plano.
    dia: str | None


class TarifasOut(BaseModel):
    rotina: int
    tarefa: int
    captura: int
    fechamento: int
    shutdown: int
    despejo: int


class PunicaoOut(BaseModel):
    limiar_furos: int
    janela: str
    desconto_padrao: int
    teto_semanal: int


class NiveisOut(BaseModel):
    limiares: list[int] = Field(min_length=1)


class CicloOut(BaseModel):
    semanas: int
    inicio: str


class StagingOut(BaseModel):
    dias_para_alerta: int


class ShutdownOut(BaseModel):
    prioridades: int


class ParametrosOut(BaseModel):
    """Como o SISTEMA funciona. Como VOCÊ está continua em /pontos."""
    tarifas: TarifasOut
    punicao: PunicaoOut
    niveis: NiveisOut
    ciclo: CicloOut
    staging: StagingOut
    shutdown: ShutdownOut
    areas: list[str] = Field(min_length=1)
    ritos: list[RitoOut] = Field(min_length=1)
```

E a rota:

```python
@app.get("/wiki/parametros", response_model=ParametrosOut)
async def wiki_parametros(_=Depends(require_auth)) -> ParametrosOut:
    """Read-only, sem estado do usuário. NENHUM literal aqui: tudo vem de
    settings, de ritos.json ou de constante já canônica do BFF."""
    return ParametrosOut(
        tarifas=TarifasOut(
            rotina=settings.pontos_por_rotina,
            tarefa=settings.pontos_por_tarefa,
            captura=settings.pontos_por_captura,
            fechamento=settings.pontos_por_fechamento,
            shutdown=settings.pontos_por_shutdown,
            despejo=settings.pontos_por_despejo,
        ),
        punicao=PunicaoOut(
            limiar_furos=settings.routine_miss_threshold,
            janela=pontos.JANELA,
            desconto_padrao=settings.desconto_padrao,
            teto_semanal=settings.teto_desconto_semanal,
        ),
        niveis=NiveisOut(limiares=settings.nivel_limiares),
        ciclo=CicloOut(semanas=settings.ciclo_semanas, inicio=settings.ciclo_inicio),
        staging=StagingOut(dias_para_alerta=settings.staging_age_days),
        shutdown=ShutdownOut(prioridades=PRIORIDADES_SHUTDOWN),
        areas=list(tasks.AREAS),
        ritos=[RitoOut(slug=r["slug"], hora=r["hora"], dia=r["dia"]) for r in ritos.RITOS],
    )
```

Confira que `Field` está importado de `pydantic` no topo do `main.py`.

- [ ] **Passo 6: gerar o schema commitado**

Rodar: `cd bff && python -m app.wiki_schema > ../app/src/wiki-schema.json`

- [ ] **Passo 7: rodar e ver passar**

Rodar: `cd bff && python -m pytest tests/test_wiki_parametros.py -q`
Esperado: PASS, 7 testes. Se `test_so_usa_o_subconjunto_do_caminhador` falhar, o modelo ganhou uma
construção que o caminhador não sabe validar — **isso é o teste funcionando**: ou simplifique o modelo,
ou estenda `PALAVRAS` e o caminhador da tarefa 5 juntos.

- [ ] **Passo 8: commitar**

```bash
git add bff/app/wiki_schema.py bff/app/main.py bff/app/pontos.py bff/tests/test_wiki_parametros.py app/src/wiki-schema.json
git commit -m "feat(escritorio): uma rota que diz como o sistema funciona, sem literal nenhum"
```

---

## Tarefa 5 — `parametrosCore.ts`, o núcleo puro

**Arquivos:**
- Criar: `app/src/parametrosCore.ts`
- Testar: `app/tests/parametrosCore.test.mjs`

**Interfaces:**
- Consome: `app/src/wiki-schema.json` (tarefa 4).
- Produz: `Params`, `Fonte`, `Decisao`, `PortaCache`, `DEFAULT_PARAMS`, `validar`, `decidir`,
  `aplicar`, `minutos`, `fonteParaWiki`. As tarefas 6, 7 e 8 dependem destes nomes.

**Regra de ouro deste módulo:** nenhum import de valor além do JSON do schema. Lógica pura, testável em
`.mjs` sem bundler.

- [ ] **Passo 1: escrever o teste que falha**

`app/tests/parametrosCore.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_PARAMS, aplicar, decidir, fonteParaWiki, minutos, validar,
} from "../src/parametrosCore.ts";

const BOM = JSON.parse(JSON.stringify(DEFAULT_PARAMS));

function porta(inicial = null) {
  const estado = { valor: inicial, escritas: [], apagou: false };
  return {
    estado,
    ler: async () => estado.valor,
    gravar: async (v) => { estado.valor = v; estado.escritas.push(v); },
    apagar: async () => { estado.valor = null; estado.apagou = true; },
  };
}

const ok = (corpo) => ({ resposta: { ok: true, corpo }, cache: null });
const falha = (status, cache = null) => ({ resposta: { ok: false, status }, cache });
const envelope = (params, salvoEm = "2026-08-11T10:00:00.000Z") => ({ params, salvoEm });

// ---- validar ----
test("validar aceita um payload completo", () => {
  assert.deepEqual(validar(BOM), BOM);
});

test("validar recusa payload parcial, tipo errado, nulo e vazio", () => {
  const semTarifas = { ...BOM }; delete semTarifas.tarifas;
  assert.equal(validar(semTarifas), null);
  assert.equal(validar({ ...BOM, ritos: [{ slug: "x", hora: 530, dia: null }] }), null);
  assert.equal(validar(null), null);
  assert.equal(validar({ ...BOM, niveis: { limiares: [] } }), null);   // minItems
  assert.equal(validar({ ...BOM, ritos: [] }), null);                  // minItems
});

test("validar aceita dia nulo e recusa dia numérico", () => {
  assert.ok(validar({ ...BOM, ritos: [{ slug: "x", hora: "05:30", dia: null }] }));
  assert.equal(validar({ ...BOM, ritos: [{ slug: "x", hora: "05:30", dia: 3 }] }), null);
});

// ---- decidir ----
test("200 válido: fonte fresca e grava", () => {
  const d = decidir(ok(BOM));
  assert.equal(d.fonte.tipo, "fresco");
  assert.equal(d.cache, "gravar");
});

test("200 inválido não toca no cache bom", () => {
  const d = decidir({ resposta: { ok: true, corpo: { lixo: 1 } }, cache: envelope(BOM) });
  assert.equal(d.fonte.tipo, "cache");
  assert.equal(d.cache, "manter");
});

test("rede caiu com cache: usa cache com a data", () => {
  const d = decidir(falha(null, envelope(BOM)));
  assert.equal(d.fonte.tipo, "cache");
  assert.equal(d.fonte.salvoEm, "2026-08-11T10:00:00.000Z");
  assert.equal(d.cache, "manter");
});

test("rede caiu sem cache: cai no embutido, rotulado padrao", () => {
  const d = decidir(falha(null));
  assert.equal(d.fonte.tipo, "padrao");
  assert.deepEqual(d.fonte.params, DEFAULT_PARAMS);
  assert.equal(d.cache, "manter");
});

test("padrao nunca é confundido com fresco nem com cache", () => {
  assert.equal(decidir(ok(BOM)).fonte.tipo, "fresco");
  assert.equal(decidir(falha(null, envelope(BOM))).fonte.tipo, "cache");
  assert.equal(decidir(falha(null)).fonte.tipo, "padrao");
});

test("401 com cache continua legível; sem cache vira sessao", () => {
  assert.equal(decidir(falha(401, envelope(BOM))).fonte.tipo, "cache");
  assert.deepEqual(decidir(falha(401)).fonte, { tipo: "indisponivel", motivo: "sessao" });
});

test("cache sem salvoEm ou com salvoEm não-ISO é descartado", () => {
  for (const ruim of [{ params: BOM }, envelope(BOM, "ontem"), envelope(BOM, "")]) {
    const d = decidir({ resposta: { ok: false, status: null }, cache: ruim });
    assert.equal(d.fonte.tipo, "padrao");   // cache ruim não conta como cache
    assert.equal(d.cache, "descartar");
  }
});

test("precedência: resposta válida grava mesmo com cache corrompido", () => {
  const d = decidir({ resposta: { ok: true, corpo: BOM }, cache: { params: BOM } });
  assert.equal(d.fonte.tipo, "fresco");
  assert.equal(d.cache, "gravar");
});

// ---- aplicar ----
test("aplicar grava, mantém e apaga conforme o comando", async () => {
  const g = porta();
  await aplicar({ fonte: { tipo: "fresco", params: BOM }, cache: "gravar" }, g);
  assert.equal(g.estado.escritas.length, 1);
  assert.equal(g.estado.valor.params.tarifas.rotina, BOM.tarifas.rotina);
  assert.ok(g.estado.valor.salvoEm, "gravou sem salvoEm");

  const m = porta(envelope(BOM));
  await aplicar({ fonte: { tipo: "cache", params: BOM, salvoEm: "x" }, cache: "manter" }, m);
  assert.equal(m.estado.escritas.length, 0);
  assert.equal(m.estado.apagou, false);

  const a = porta(envelope(BOM));
  await aplicar({ fonte: { tipo: "indisponivel", motivo: "sessao" }, cache: "descartar" }, a);
  assert.equal(a.estado.apagou, true);
});

test("aplicar não propaga falha de escrita", async () => {
  const quebrada = { ler: async () => null, gravar: async () => { throw new Error("cheio"); }, apagar: async () => {} };
  await aplicar({ fonte: { tipo: "fresco", params: BOM }, cache: "gravar" }, quebrada);
});

test("duas decisões seguidas gravam em ordem", async () => {
  const p = porta();
  const a = { ...BOM, tarifas: { ...BOM.tarifas, rotina: 1 } };
  const b = { ...BOM, tarifas: { ...BOM.tarifas, rotina: 2 } };
  await aplicar({ fonte: { tipo: "fresco", params: a }, cache: "gravar" }, p);
  await aplicar({ fonte: { tipo: "fresco", params: b }, cache: "gravar" }, p);
  assert.deepEqual(p.estado.escritas.map((e) => e.params.tarifas.rotina), [1, 2]);
});

// ---- minutos e fonteParaWiki ----
test("minutos converte HH:MM", () => {
  assert.equal(minutos("00:00"), 0);
  assert.equal(minutos("18:30"), 1110);
  assert.equal(minutos("23:59"), 1439);
});

test("fonteParaWiki recusa o padrão e preserva o resto", () => {
  assert.deepEqual(fonteParaWiki({ tipo: "padrao", params: BOM }),
                   { tipo: "indisponivel", motivo: "sem-cache" });
  for (const f of [{ tipo: "fresco", params: BOM },
                   { tipo: "cache", params: BOM, salvoEm: "z" },
                   { tipo: "indisponivel", motivo: "sessao" }]) {
    assert.deepEqual(fonteParaWiki(f), f);
  }
});

test("DEFAULT_PARAMS é um Params válido", () => {
  assert.ok(validar(DEFAULT_PARAMS), "o embutido não passa no próprio schema");
});
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `cd app && node --test tests/parametrosCore.test.mjs`
Esperado: FAIL — o módulo não existe.

- [ ] **Passo 3: implementar `app/src/parametrosCore.ts`**

```ts
// Núcleo dos parâmetros do sistema: tipos, validação, política e efeito.
// Puro e sem import de valor além do schema — o teste roda em .mjs sem bundler.
//
// O schema é O validador, não um segundo lugar onde as regras estão escritas:
// `validar` caminha sobre ele. Antes havia uma implementação manual em TS e um
// teste tentando provar que as duas concordavam.
import schema from "./wiki-schema.json";

export type Rito = { slug: string; hora: string; dia: string | null };
export type Params = {
  tarifas: { rotina: number; tarefa: number; captura: number; fechamento: number; shutdown: number; despejo: number };
  punicao: { limiar_furos: number; janela: string; desconto_padrao: number; teto_semanal: number };
  niveis: { limiares: number[] };
  ciclo: { semanas: number; inicio: string };
  staging: { dias_para_alerta: number };
  shutdown: { prioridades: number };
  areas: string[];
  ritos: Rito[];
};

export type Fonte =
  | { tipo: "fresco"; params: Params }
  | { tipo: "cache"; params: Params; salvoEm: string }
  | { tipo: "padrao"; params: Params }
  | { tipo: "indisponivel"; motivo: "sem-cache" | "sessao" };

export type Decisao = { fonte: Fonte; cache: "gravar" | "manter" | "descartar" };

export type Entrada = {
  resposta: { ok: true; corpo: unknown } | { ok: false; status: number | null };
  cache: unknown;
};

export type PortaCache = {
  ler(): Promise<unknown>;
  gravar(v: unknown): Promise<void>;
  apagar(): Promise<void>;
};

// O que o app mostra antes de falar com o servidor. NÃO é uma segunda fonte
// silenciosa: vira `Fonte.padrao`, a tela avisa, e a wiki recusa.
export const DEFAULT_PARAMS: Params = {
  tarifas: { rotina: 20, tarefa: 10, captura: 5, fechamento: 80, shutdown: 30, despejo: 40 },
  punicao: { limiar_furos: 3, janela: "semana_iso", desconto_padrao: 60, teto_semanal: 200 },
  niveis: { limiares: [700, 1700, 3400, 6800] },
  ciclo: { semanas: 12, inicio: "2026-07-06" },
  staging: { dias_para_alerta: 3 },
  shutdown: { prioridades: 3 },
  areas: ["Trabalho", "Staging", "Corpo", "Saúde Mental", "Responsabilidade",
          "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer"],
  ritos: [
    { slug: "toque", hora: "05:30", dia: null },
    { slug: "checkin", hora: "08:20", dia: null },
    { slug: "jornal", hora: "08:30", dia: null },
    { slug: "digest", hora: "09:00", dia: null },
    { slug: "shutdown", hora: "19:00", dia: null },
    { slug: "closing", hora: "21:00", dia: null },
    { slug: "review", hora: "20:00", dia: "domingo" },
  ],
};

type No = {
  type?: string; properties?: Record<string, No>; required?: string[];
  items?: No; minItems?: number; enum?: unknown[]; nullable?: boolean;
};

function confere(valor: unknown, no: No): boolean {
  if (valor === null) return no.nullable === true;
  switch (no.type) {
    case "object": {
      if (typeof valor !== "object" || Array.isArray(valor)) return false;
      const obj = valor as Record<string, unknown>;
      for (const chave of no.required ?? []) if (!(chave in obj)) return false;
      for (const [chave, filho] of Object.entries(no.properties ?? {})) {
        if (chave in obj && !confere(obj[chave], filho)) return false;
      }
      return true;
    }
    case "array":
      if (!Array.isArray(valor)) return false;
      if (no.minItems !== undefined && valor.length < no.minItems) return false;
      return no.items ? valor.every((v) => confere(v, no.items as No)) : true;
    case "integer":
      return typeof valor === "number" && Number.isInteger(valor);
    case "number":
      return typeof valor === "number";
    case "string":
      return typeof valor === "string" && (!no.enum || no.enum.includes(valor));
    case "boolean":
      return typeof valor === "boolean";
    default:
      return true;
  }
}

export function validar(bruto: unknown): Params | null {
  return confere(bruto, schema as No) ? (bruto as Params) : null;
}

function doCache(cru: unknown): { params: Params; salvoEm: string } | null {
  if (!cru || typeof cru !== "object") return null;
  const env = cru as { params?: unknown; salvoEm?: unknown };
  if (typeof env.salvoEm !== "string" || Number.isNaN(Date.parse(env.salvoEm))) return null;
  const params = validar(env.params);
  return params ? { params, salvoEm: env.salvoEm } : null;
}

export function decidir(e: Entrada): Decisao {
  // Precedência: resposta válida SEMPRE grava. Só sem resposta válida o cache
  // ruim é descartado -- senão um 200 bom com cache corrompido apagaria em vez
  // de persistir.
  if (e.resposta.ok) {
    const params = validar(e.resposta.corpo);
    if (params) return { fonte: { tipo: "fresco", params }, cache: "gravar" };
  }
  const bom = doCache(e.cache);
  if (bom) return { fonte: { tipo: "cache", ...bom }, cache: "manter" };

  // Sem resposta E sem cache: 401 significa app deslogado (o fluxo de login
  // assume), qualquer outra falha cai no embutido -- rotulado `padrao`, com
  // indicador na tela, e recusado pela wiki via fonteParaWiki.
  // `decidir` produz `padrao` ELA MESMA: se o provider fizesse isso, teria
  // política própria, e política mora aqui (WIKI-SPEC §3.3).
  const status = e.resposta.ok ? null : e.resposta.status;
  const cache = e.cache == null ? "manter" : "descartar";
  if (status === 401) return { fonte: { tipo: "indisponivel", motivo: "sessao" }, cache };
  return { fonte: { tipo: "padrao", params: DEFAULT_PARAMS }, cache };
}

export async function aplicar(d: Decisao, porta: PortaCache): Promise<void> {
  // Falha de armazenamento não pode derrubar a tela: a fonte já foi decidida.
  try {
    if (d.cache === "gravar" && "params" in d.fonte) {
      await porta.gravar({ params: d.fonte.params, salvoEm: new Date().toISOString() });
    } else if (d.cache === "descartar") {
      await porta.apagar();
    }
  } catch {
    // silêncio deliberado: ver acima
  }
}

export function minutos(hora: string): number {
  const [h, m] = hora.split(":");
  return Number(h) * 60 + Number(m);
}

/** A wiki é a única tela que promete ser a referência: ela recusa o embutido. */
export function fonteParaWiki(f: Fonte): Fonte {
  return f.tipo === "padrao" ? { tipo: "indisponivel", motivo: "sem-cache" } : f;
}
```

- [ ] **Passo 4: rodar e ver passar**

Rodar: `cd app && node --test tests/parametrosCore.test.mjs`
Esperado: PASS.

Se `resolveJsonModule` reclamar no typecheck, acrescente `"resolveJsonModule": true` ao
`compilerOptions` do `app/tsconfig.json`.

- [ ] **Passo 5: typecheck**

Rodar: `cd app && npm run typecheck`
Esperado: sem erros.

- [ ] **Passo 6: commitar**

```bash
git add app/src/parametrosCore.ts app/tests/parametrosCore.test.mjs app/tsconfig.json
git commit -m "feat(escritorio): o schema deixa de ser so contrato e vira o validador"
```

---

## Tarefa 6 — o provider

**Arquivos:**
- Criar: `app/src/parametros.tsx`
- Modificar: `app/src/api.ts` (acrescenta `getParametros`)
- Modificar: `app/App.tsx` (embrulha a árvore)

**Interfaces:**
- Consome: tudo de `parametrosCore` (tarefa 5); `authHeaders`/`getBffUrl` de `api.ts`.
- Produz: `useParametros(): Fonte`, `useParams(): Params` (atalho: os params da fonte, ou
  `DEFAULT_PARAMS` quando `indisponivel`), `useRevalidar(): () => void`. As tarefas 7 e 8 usam
  `useParams()`.

**Por que o provider é o único dono do fetch:** se a tela também buscasse, a wiki poderia receber
valores novos enquanto a Mesa continuasse no anterior — dois donos, duas verdades.

- [ ] **Passo 1: acrescentar o fetch em `api.ts`**

Depois de `getPontos`:

```ts
/** Como o SISTEMA funciona (tarifas, limiares, horários). O SEU estado é /pontos.
 *  Devolve o corpo cru: quem valida é o parametrosCore, contra o schema. */
export async function getParametros(): Promise<{ ok: boolean; corpo?: unknown; status: number | null }> {
  try {
    const base = await getBffUrl();
    const r = await fetch(`${base}/wiki/parametros`, { headers: await authHeaders() });
    if (!r.ok) return { ok: false, status: r.status };
    return { ok: true, corpo: await r.json(), status: r.status };
  } catch {
    return { ok: false, status: null };
  }
}
```

- [ ] **Passo 2: implementar `app/src/parametros.tsx`**

```tsx
// O ÚNICO dono dos parâmetros do app: busca, valida, cacheia e revalida.
// Nenhuma tela faz fetch disto por conta própria -- nem a wiki.
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AppState } from "react-native";

import { getParametros } from "./api";
import {
  DEFAULT_PARAMS, Fonte, Params, PortaCache, aplicar, decidir,
} from "./parametrosCore";
import { deleteItemAsync, getItemAsync, setItemAsync } from "./storage";

const CHAVE = "wiki_parametros_v1";

const porta: PortaCache = {
  async ler() {
    const cru = await getItemAsync(CHAVE);
    if (!cru) return null;
    try { return JSON.parse(cru); } catch { return null; }
  },
  gravar: (v) => setItemAsync(CHAVE, JSON.stringify(v)),
  apagar: () => deleteItemAsync(CHAVE),
};

const Ctx = createContext<{ fonte: Fonte; revalidar: () => void }>({
  fonte: { tipo: "padrao", params: DEFAULT_PARAMS },
  revalidar: () => {},
});

export function ParametrosProvider({ children }: { children: React.ReactNode }) {
  const [fonte, setFonte] = useState<Fonte>({ tipo: "padrao", params: DEFAULT_PARAMS });

  const buscar = useCallback(async () => {
    const resposta = await getParametros();
    const cache = await porta.ler();
    const decisao = decidir({
      resposta: resposta.ok
        ? { ok: true, corpo: resposta.corpo }
        : { ok: false, status: resposta.status },
      cache,
    });
    await aplicar(decisao, porta);
    // Nenhum `if` aqui, de propósito: a política inteira é de `decidir`,
    // inclusive cair no embutido. Provider que decide é provider com política.
    setFonte(decisao.fonte);
  }, []);

  useEffect(() => { void buscar(); }, [buscar]);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (s) => { if (s === "active") void buscar(); });
    return () => sub.remove();
  }, [buscar]);

  return <Ctx.Provider value={{ fonte, revalidar: () => void buscar() }}>{children}</Ctx.Provider>;
}

export function useParametros(): Fonte {
  return useContext(Ctx).fonte;
}

export function useRevalidar(): () => void {
  return useContext(Ctx).revalidar;
}

/** Atalho para quem só quer os números. `indisponivel` cai no embutido. */
export function useParams(): Params {
  const f = useParametros();
  return "params" in f ? f.params : DEFAULT_PARAMS;
}
```

- [ ] **Passo 3: embrulhar a árvore em `App.tsx`**

Importe `ParametrosProvider` e envolva o conteúdo raiz que hoje é renderizado — o mesmo nível onde
ficam os outros providers, se houver, ou logo dentro do container mais externo.

- [ ] **Passo 4: typecheck e suíte**

Rodar: `cd app && npm run check`
Esperado: sem erros de tipo; testes passam.

- [ ] **Passo 5: commitar**

```bash
git add app/src/parametros.tsx app/src/api.ts app/App.tsx
git commit -m "feat(escritorio): um dono so para os parametros do app"
```

---

## Tarefa 7 — `mesaView` e `homeAction` recebem os horários

**Arquivos:**
- Modificar: `app/src/mesaView.ts:70,74`
- Modificar: `app/src/homeAction.ts:92-135`
- Modificar: `app/src/screens/Mesa.tsx`, `app/src/screens/Home.tsx` (passam a tabela)
- Testar: `app/tests/mesaView.test.mjs`, `app/tests/homeAction.test.mjs`

**Interfaces:**
- Consome: `Rito`, `minutos` de `parametrosCore`; `useParams()` do provider.
- Produz: `montarMesa(sinais, points, ritos)`, `actionForAt(abertura, signals, ritos, now?)`.

**Cuidado com a ordem do parâmetro:** `actionForAt` tem `now` com valor default e os testes passam
`now` posicionalmente. `ritos` entra **antes** de `now`, e todas as chamadas nos testes precisam ser
atualizadas — são muitas. Não tente inserir no fim.

- [ ] **Passo 1: escrever os testes que falham**

Em `app/tests/homeAction.test.mjs`, acrescente no topo uma tabela e um helper:

```js
import { minutos } from "../src/parametrosCore.ts";

const RITOS = [
  { slug: "toque", hora: "05:30", dia: null },
  { slug: "checkin", hora: "08:20", dia: null },
  { slug: "jornal", hora: "08:30", dia: null },
  { slug: "digest", hora: "09:00", dia: null },
  { slug: "shutdown", hora: "19:00", dia: null },
  { slug: "closing", hora: "21:00", dia: null },
  { slug: "review", hora: "20:00", dia: "domingo" },
];
const com = (over) => RITOS.map((r) => ({ ...r, ...(over[r.slug] ?? {}) }));
```

E os testes novos:

```js
test("os limiares de rito seguem a tabela: shutdown movido move o hero", () => {
  const ritos = com({ shutdown: { hora: "18:00" } });
  const as18 = at("2026-07-13T18:05:00-03:00");
  assert.equal(actionForAt(null, empty, RITOS, as18).target, "tarefas");
  assert.equal(actionForAt(null, empty, ritos, as18).target, "shutdown");
});

test("rito com minuto não-zero: antes, no instante e depois", () => {
  const ritos = com({ shutdown: { hora: "18:30" } });
  const alvo = (hhmm) => actionForAt(null, empty, ritos, at(`2026-07-13T${hhmm}:00-03:00`)).target;
  assert.equal(alvo("18:29"), "tarefas");
  assert.equal(alvo("18:30"), "shutdown");
  assert.equal(alvo("18:31"), "shutdown");
});

test("o domingo deriva review menos 3h", () => {
  const cedo = com({ review: { hora: "18:00" } });   // limiar vira 15:00
  const as16 = at("2026-07-12T16:00:00-03:00");      // domingo
  assert.notEqual(actionForAt(null, empty, RITOS, as16).target, "revisao");
  assert.equal(actionForAt(null, empty, cedo, as16).target, "revisao");
});

test("os dois prazos NÃO derivam de rito nenhum", () => {
  const tarde = com({ toque: { hora: "09:00" }, checkin: { hora: "11:00" } });
  const as7 = at("2026-07-13T07:00:00-03:00");
  assert.equal(actionForAt(null, empty, RITOS, as7).target, "abertura");
  assert.equal(actionForAt(null, empty, tarde, as7).target, "abertura");
});

test("minutos e a tabela concordam", () => {
  assert.equal(minutos("18:30"), 1110);
});
```

Em `app/tests/mesaView.test.mjs`, acrescente:

```js
test("a hora exibida vem da tabela, não de literal", () => {
  const ritos = [
    { slug: "shutdown", hora: "18:00", dia: null },
    { slug: "closing", hora: "22:00", dia: null },
  ];
  const grupos = montarMesa(sinais({ shutdownFeito: false }), POINTS, ritos);
  assert.equal(item(grupos, "shutdown").contador, "18h");
  assert.equal(item(grupos, "fechar").contador, "22h");
  assert.match(item(grupos, "shutdown").sub, /18h/);
});
```

Atualize **todas** as chamadas existentes de `montarMesa(...)` e `actionForAt(...)` nos dois arquivos
de teste para passar a tabela.

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `cd app && node --test tests/homeAction.test.mjs tests/mesaView.test.mjs`
Esperado: FAIL.

- [ ] **Passo 3: implementar em `mesaView.ts`**

Acrescente ao topo, junto do `PointsTable`:

```ts
// A hora entra por parâmetro, pelo mesmo motivo que a tabela de pontos: o
// mesaView escrevia "19h" e "21h" à mão, e mudar o rito deixava a Mesa mentindo.
export type Rito = { slug: string; hora: string; dia: string | null };

function horaCurta(ritos: Rito[], slug: string): string {
  const r = ritos.find((x) => x.slug === slug);
  if (!r) return "";
  const [h, m] = r.hora.split(":");
  return m === "00" ? `${Number(h)}h` : `${Number(h)}h${m}`;
}
```

Troque a assinatura para `montarMesa(sinais: MesaSinais, points: PointsTable, ritos: Rito[])`, e as
duas linhas:

```ts
  if (sinais.shutdownFeito === false) {
    const h = horaCurta(ritos, "shutdown");
    precisa.push(item("shutdown", "Shutdown", `rito das ${h} · fecha o trabalho`, h));
  }
  const hFechar = horaCurta(ritos, "closing");
  precisa.push(item("fechar", "Fechar o dia", `rito das ${hFechar} · vale +${points.fechamento}`, hFechar));
```

- [ ] **Passo 4: implementar em `homeAction.ts`**

Assinatura: `actionForAt(abertura, signals, ritos: Rito[], now = new Date())`.

No corpo, troque `const hour = now.getHours();` por:

```ts
  const agora = now.getHours() * 60 + now.getMinutes();
  const em = (slug: string) => {
    const r = ritos.find((x) => x.slug === slug);
    if (!r) return Number.POSITIVE_INFINITY;
    const [h, m] = r.hora.split(":");
    return Number(h) * 60 + Number(m);
  };
```

E as condições:

| Antes | Depois | Por quê |
|---|---|---|
| `hour < 8` | `agora < 8 * 60` | **Prazo** para abrir o dia, não o horário do toque |
| `hour < 12` | `agora < 12 * 60` | Prazo do check-in, não o horário dele |
| `hour < 19` | `agora < em("shutdown")` | Deriva |
| `sunday && hour >= 17` | `sunday && agora >= em("review") - 180` | Deriva: 3h de antecedência |
| `hour >= 19 && hour < 21` | `agora >= em("shutdown") && agora < em("closing")` | Deriva |
| `hour >= 21` | `agora >= em("closing")` | Deriva |

E na linha 131 troque o `eyebrow` literal `"rito das 21h"` por `` `rito das ${horaCurta(ritos, "closing")}` ``
— reaproveite o helper exportando-o de `mesaView.ts` ou duplicando-o localmente (são 4 linhas; duplicar
é aceitável para manter os dois módulos sem import de valor entre si).

Comente os dois prazos no código: **prazo**, não janela de antecedência. Nomear uma relação com um rito
e não derivá-la foi um defeito real que a revisão pegou.

- [ ] **Passo 5: ligar as telas**

Em `Mesa.tsx` e `Home.tsx`, importe `useParams` de `../parametros` e passe `params.ritos` (e
`params.tarifas` no lugar de `POINTS`, já preparando a tarefa 8) para `montarMesa` e `actionForAt`.

- [ ] **Passo 6: rodar e ver passar**

Rodar: `cd app && npm run check`
Esperado: PASS, incluindo as 2160 combinações do `mesaView`.

- [ ] **Passo 7: commitar**

```bash
git add app/src/mesaView.ts app/src/homeAction.ts app/src/screens/Mesa.tsx app/src/screens/Home.tsx app/tests/mesaView.test.mjs app/tests/homeAction.test.mjs
git commit -m "fix(escritorio): a Mesa prometia 19h sem saber que horas o rito era"
```

---

## Tarefa 8 — os 7 call sites de `POINTS.` e a guarda

**Arquivos:**
- Modificar: `app/src/screens/Capture.tsx:1698`, `Fechar.tsx:360,369,418`, `Tasks.tsx:72,107,416`
- Modificar: `app/src/theme.ts:73-80` (apaga `POINTS`)
- Modificar: `app/tests/mesaView.test.mjs`, `app/tests/closingPoints.test.mjs` (importam a semente do core)
- Testar: `app/tests/migracaoPoints.test.mjs`

**Interfaces:**
- Consome: `useParams()` (tarefa 6).
- Produz: nada novo. Esta tarefa **fecha** a fatia.

**Atenção ao `despejoBonus`:** o nome no `theme.ts` era `despejoBonus`; no `Params` é `tarifas.despejo`.
É o único que muda de nome — `Fechar.tsx:418` e `closingPoints.ts` usam ele.

**Atenção ao `PointsTable`:** `mesaView.PointsTable` e `closingPoints` são estruturais e **não** têm
`despejoBonus`. `params.tarifas` tem `despejo` a mais, o que é atribuível — não quebra.

- [ ] **Passo 1: escrever a guarda que falha**

`app/tests/migracaoPoints.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// `DEFAULT_PARAMS`, em parametrosCore.ts, é a ÚNICA semente das tarifas no app.
// `POINTS` deixou de existir -- manter os dois seria recriar a duplicação que esta
// fatia mata --, então NADA em src/ pode citá-lo. Sem esta guarda, um call site
// esquecido passa despercebido e a fonte única fica pela metade.

function arquivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return arquivos(p);
    return /\.(ts|tsx)$/.test(n) ? [p] : [];
  });
}

test("POINTS não existe mais em lugar nenhum", () => {
  const infratores = arquivos("src")
    .filter((p) => /\bPOINTS\b/.test(readFileSync(p, "utf8")));
  assert.deepEqual(infratores, [], `ainda leem POINTS: ${infratores.join(", ")}`);
});
```

- [ ] **Passo 2: rodar e ver falhar**

Rodar: `cd app && node --test tests/migracaoPoints.test.mjs`
Esperado: FAIL listando `Capture.tsx`, `Fechar.tsx`, `Tasks.tsx`, `Mesa.tsx`, `Home.tsx`.

- [ ] **Passo 3: migrar os call sites**

Em cada tela, troque o import de `POINTS` por `useParams` e leia `params.tarifas`:

| Arquivo:linha | De | Para |
|---|---|---|
| `Capture.tsx:1698` | `+{POINTS.captura}` | `+{tarifas.captura}` |
| `Fechar.tsx:360` | `feitas * POINTS.rotina` | `feitas * tarifas.rotina` |
| `Fechar.tsx:369` | `points={POINTS.rotina}` | `points={tarifas.rotina}` |
| `Fechar.tsx:418` | `+${POINTS.despejoBonus} bônus` | `+${tarifas.despejo} bônus` |
| `Tasks.tsx:72,107,416` | `POINTS.tarefa` | `tarifas.tarefa` |

Em `Fechar.tsx:218` e `:428`/`:458`, `closingReward`/`closingLabel` recebem `POINTS` por parâmetro —
passe `tarifas`. Em `Mesa.tsx` e `Home.tsx` a troca já foi feita na tarefa 7.

Em cada componente, no topo: `const { tarifas } = useParams();`

- [ ] **Passo 4: apagar `POINTS` do `theme.ts`**

Remova o bloco `export const POINTS = { ... } as const;` (linhas 73–80) **inteiro**. Não o transforme
em "semente": `DEFAULT_PARAMS.tarifas` já é a semente, e manter os dois seria recriar a duplicação de
seis números que esta fatia inteira existe para matar.

Os dois testes que importavam `POINTS` de propósito — para prender os valores de produção ao teste —
passam a importar de `parametrosCore`:

```js
// em app/tests/mesaView.test.mjs e app/tests/closingPoints.test.mjs
import { DEFAULT_PARAMS } from "../src/parametrosCore.ts";
const POINTS = DEFAULT_PARAMS.tarifas;
```

O `despejoBonus` vira `despejo` também aqui. `closingPoints.ts` importa `typeof POINTS` como tipo —
troque por `type PointsTable = typeof DEFAULT_PARAMS.tarifas`, ou pelo tipo estrutural que ele já
declara.

- [ ] **Passo 5: o indicador de valores padrão**

Na Home, quando `useParametros().tipo === "padrao"`, desenhe uma linha discreta no topo:
`valores padrão · sem conexão`, em `textMuted`, no mesmo estilo do badge de fila offline que a Capturar
já usa. Um indicador no app inteiro, não um selo por número.

- [ ] **Passo 6: rodar tudo**

Rodar: `cd app && npm run check`
Esperado: PASS, incluindo a guarda.

Rodar: `cd bff && python -m pytest -q`
Esperado: PASS.

- [ ] **Passo 7: verificar no aparelho — o aceite da 1A**

1. Mudar `pontos_por_rotina` para `25` no `.env`, reiniciar o BFF, abrir o app: **Mesa, Fechar e
   Tarefas** mostram 25. Voltar para 20.
2. Mudar a hora do `closing` no `ritos.json` para `20:30`, rodar `sync-cron.ps1`, reiniciar o BFF:
   o Agendador mostra 20:30, o push diz `20h30`, a Mesa diz `20h30`, o hero muda às 20:30.
   Voltar para `21:00` e rodar o sync de novo.
3. Desligar o BFF, apagar o app e reinstalar sem rede: Mesa e Home funcionam com os valores embutidos
   **e o indicador está visível**.
4. Ligar o BFF sem sair da tela, tirar o app do foco e voltar: o indicador some.

- [ ] **Passo 8: commitar**

```bash
git add app/src/screens/Capture.tsx app/src/screens/Fechar.tsx app/src/screens/Tasks.tsx app/src/screens/Home.tsx app/src/theme.ts app/src/closingPoints.ts app/tests/migracaoPoints.test.mjs app/tests/mesaView.test.mjs app/tests/closingPoints.test.mjs
git commit -m "feat(escritorio): as tarifas do app passam a vir do servidor, e uma guarda cobra isso"
```

---

## Definição de pronto (1A)

- [ ] `cd bff && python -m pytest -q` passa
- [ ] `cd app && npm run check` passa
- [ ] Os quatro drills do Passo 7 da tarefa 8, feitos no aparelho
- [ ] `grep -rnE '"(19h|21h|5h30|8h20)"' app/src/` não devolve nada
- [ ] `grep -rn "POINTS" app/src/` não devolve nada
- [ ] `WIKI-SPEC.md` §12 atualizado: 1A entregue, com a data

Só então comece a 1B.

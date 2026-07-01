---
artifact: skill-spec
capability: escritorio
skill: reminder-digest
status: baseline
source_refs: [../../cutuca/src/cutuca/cadence.py, ../../cutuca/src/cutuca/nudge.py, DECISIONS.md]
implements: RUNBOOK.md Stage 5
---

# SKILL SPEC — reminder-digest (o "cutuca" como skill do Hermes)

Porta as regras **testadas** do cutuca (50 testes) para uma skill de cron do Hermes.
A lógica é determinística — o modelo só formata/entrega; a decisão de "cobrar ou não" é
código/regra, não achismo do LLM.

## Trigger
- Cron do Hermes. **Default `08:00`** (America/Sao_Paulo); opcional `13:00` pra atrasados.
- Valores em config, não hardcode (D-7).

## Input
- Via **ClickUp MCP**: ler tasks das Spaces das áreas (`Trabalho, Finanças, Saúde, Pessoal`),
  ou um subconjunto configurável. Campos usados: `name`, `status`, `assignees`, `due_date`,
  `date_updated`, e (recorrentes) última conclusão.

## Regra de seleção — `cobrar_se` (cobra se QUALQUER uma bater)
Para cada task **não fechada** (pular status: closed/complete/done/concluído/cancelado/…):
1. **vence em ≤ N dias** — `0 ≤ (due_date − hoje) ≤ vence_em_dias` (default `vence_em_dias=0` = hoje).
2. **atrasada** — `due_date < hoje` (se `atrasada=true`, default).
3. **parada** — `hoje − date_updated ≥ sem_update_dias` (default `3`).

## Dedupe (sem spam)
- Chave = `(task_id, dia)`. Não repetir a mesma task no mesmo dia (idempotente).
- Estado do dedupe é **andaime** (SQLite/arquivo local/memória do Hermes) — NÃO é dado canônico,
  então não fere "vidro não arquivo".
- Dia seguinte a task reaparece (persistência); só não repete idêntico no mesmo dia.

## Escala de tom — `tone(days_overdue)` (se `escala_tom=true`)
| dias atrasado | rótulo | marcador |
|---|---|---|
| ≤ 0 | no_prazo | 🟡 |
| 1–2 | leve | 🟠 |
| 3–6 | firme | 🔴 |
| ≥ 7 | urgente | 🚨 |

## Output (digest)
- Entregue **só pro dono**, no Telegram (canal do Hermes).
- **Agrupado por área** (Space), e dentro de cada área **mais atrasada primeiro**.
- Cada linha: `{marcador} {nome} — {assignee|—} · {estado}` onde estado =
  `atrasada Xd` / `vence hoje` / `vence em Xd` / `parada há Xd`.
- Para itens com recência (saúde/hábitos): incluir *"última vez há Xd/meses"* quando existir.
- Sem nada a cobrar → mensagem curta "tudo em dia ✅" (ou silêncio, config).

Exemplo:
```
🔔 Cobranças de hoje (4)
Saúde
  🚨 Dentista — última vez há 7 meses (tá na hora)
  🟡 Treino — vence hoje
Trabalho
  🔴 Relatório — Ana · atrasada 4d
Finanças
  🟠 Fatura cartão — atrasada 2d
```

## Config (o dono gira o botão)
```yaml
digest_horarios: ["08:00"]        # + "13:00" opcional
timezone: "America/Sao_Paulo"
escala_tom: true
cobrar_se: { vence_em_dias: 0, atrasada: true, sem_update_dias: 3 }
areas: ["Trabalho", "Finanças", "Saúde", "Pessoal"]   # Spaces do ClickUp
agrupar_por_area: true
silencio_se_vazio: false
```

## Instrução de cron pro Hermes (linguagem natural + regra dura)
> "Todo dia às 08:00 (America/Sao_Paulo): via ClickUp MCP, leia as tasks das Spaces
> {areas}. Selecione as que vencem hoje, estão atrasadas, ou sem update há ≥3 dias, e não
> estão fechadas. Remova as que eu já fui avisado hoje. Agrupe por área, mais atrasada
> primeiro, com o marcador de tom pela quantidade de dias de atraso. Me mande no Telegram.
> Depois de enviar, marque essas tasks como avisadas hoje."

A regra de seleção/dedupe/tom acima é a **fonte da verdade** — o texto natural é só o gatilho.

## Falhas / bordas
- Erro de API ao ler ClickUp → pular a rodada + logar; não travar, não mandar lixo.
- Falha ao enviar → **não** marcar como avisado (pra tentar de novo).
- `owner_chat_id` ausente → logar o chat_id e não enviar.

## Referência de implementação (já testada)
- Regras: `../../cutuca/src/cutuca/cadence.py` (`needs_nudge`, `tone`, `select`).
- Orquestração/formatação: `../../cutuca/src/cutuca/nudge.py` (`run_digest`, `format_digest`).
- Dedupe: `../../cutuca/src/cutuca/state.py`.

## Aceite (Estágio 5 do RUNBOOK)
- Rodar 2× no mesmo dia → cada task cobrada 1× (dedupe). ✅
- Tom escala com dias de atraso. ✅
- Agrupado por área, mais atrasada primeiro, entregue só pro dono. ✅

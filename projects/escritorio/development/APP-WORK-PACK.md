---
artifact: work-pack
capability: escritorio-app
authored_by: invoke/plan
status: baseline
complexity: high
output_mode: single-file
source_refs: [APP-ARCHITECTURE.md, CAPTURE-GRAMMAR-SPEC.md, REMINDER-SKILL-SPEC.md, RUNBOOK.md]
---

# APP-WORK-PACK — o app próprio (cockpit)

**Objetivo:** construir o cockpit pessoal (Django + HTMX + Tailwind, PWA) como vidro sobre o
Hermes — captura (leitura #1 + tarefas/notas) e consulta (tarefas por área) — no VPS.

**Dispatch trace:** `sequence` (Hermes → app), `scu_swu_reduction` (cada tarefa = unidade mínima),
`recomposition_proof` (tarefas remontam nas views do APP-ARCHITECTURE), `validation_loop` (cada
onda tem "prove it"), `owner_boundary_check` (invoke planeja; owner/agente executa),
`residue_ledger` (deps e gaps visíveis), `execution_receipt_handoff` (passos live nomeiam o dono).

## Dependência dura
O app **precisa do Hermes de pé** (RUNBOOK estágios 0–6: VPS, Hermes, modelo+Telegram,
MCP ClickUp+GitHub, profiles, skill de lembrete). Até o app chegar em L1, **ler pela ponte**
(Telegram / Claude Code no vault). Construir a UI antes do motor = vidro sobre o nada.

## Ondas por camada (L0→L3)

### L0 — prova de encanamento (o app fala com o Hermes)
Pergunta: o app consegue mandar texto pro Hermes e ver virar coisa no vault?
- **T-A0** Scaffold Django + HTMX + Tailwind; roda no VPS atrás de HTTPS (Caddy).
- **T-A1** Auth single-user via `django.contrib.auth` (login → sessão). Segredos em `.env`.
- **T-A2** BFF: view/rota `POST /capture` que repassa texto pro Hermes (profile Leitura) via a API
  do Hermes, guardando `HERMES_API_KEY` no servidor.
- **T-A3** UI mínima: uma caixa de texto + botão enviar + área de resposta (HTMX).
- **Prove it:** logar → digitar uma nota → ela aparece no vault (via Hermes/GitHub MCP) e o app
  mostra "✅". *(desbloqueia tudo)*

### L1 — valor diário (as 2 coisas que você usa todo dia)
- **T-A4** View **Capturar-Leitura**: seletor de profile, modelo de sessão (livro abre, falas
  anexam, "compilar" finaliza), mostra itens da sessão. Usa a CAPTURE-GRAMMAR (6 modos) no Hermes.
- **T-A5** View **Tarefas**: lista por área (Trabalho/Finanças/Saúde/Pessoal) + recência ("última
  vez há X"); criar tarefa; concluir. Lê/escreve via Hermes→ClickUp MCP.
- **T-A6** Tratamento de erro/timeout (Hermes fora → mensagem clara, sem travar).
- **Prove it:** uma sessão de leitura real vira nota no vault; "me mostra Saúde" lista as tasks
  com recência; criar tarefa aparece no ClickUp.

### L2 — cockpit redondo
- **T-A7** View **Chat** (conversa livre por profile) via `/v1` do Hermes.
- **T-A8** View **Revisão**: digest do dia + itens ★ pra Anki.
- **T-A9** **PWA**: manifest + service worker (shell instalável no celular; ícone na home).
- **T-A10** Polish mobile-first + hardening de auth + logs.
- **Prove it:** instala no celular; captura e consulta pelo telefone; digest aparece.

### L3 — rodar sozinho
- **T-A11** Deploy no VPS (Caddy HTTPS, Tailscale/domínio, systemd), backups do estado de UI.
- **T-A12** Runbook de operação (subir/atualizar/rollback).
- **Prove it:** reinicia o VPS → app + Hermes sobem sozinhos; acessível do celular fora de casa.

## SWUs (núcleo)
- **SWU-APP-001** (T-A2): proxy `POST /capture` → Hermes. Aceite: texto entra, nota sai no vault.
  Write: `cockpit/capture/views.py`, `cockpit/hermes_client.py`. Verify: request autenticado → commit no vault.
- **SWU-APP-002** (T-A4): sessão de leitura (abrir com "livro", anexar, "compilar"). Aceite: 6 modos
  → nota formatada conforme CAPTURE-GRAMMAR. Write: `cockpit/reading/views.py` + templates.
- **SWU-APP-003** (T-A5): tarefas por área + recência. Aceite: lista agrupada por Space, "última vez"
  correta; criar/concluir reflete no ClickUp. Write: `cockpit/tasks/views.py`.
- **SWU-APP-004** (T-A1): auth single-user (`django.contrib.auth`) + segredos server-side. Aceite:
  sem sessão → redirect/401; chave do Hermes nunca no HTML. Write: `cockpit/settings.py`, `cockpit/accounts/`.

## Estratégia de validação
- L0/L1: testes de integração com o Hermes **mockado** (o BFF é testável sem rede); + um teste
  manual "prove it" contra o Hermes real por onda.
- Segurança: teste que a `HERMES_API_KEY` nunca aparece em resposta/HTML; rota sem sessão = 401.
- Aceite vivo (owner): capturar leitura real → nota no vault; consultar Saúde; instalar PWA.

## Distill
- Unidade mínima: cada tarefa toca um router/template. **pass**
- Recomposição: tarefas remontam nas 4 views do APP-ARCHITECTURE. **pass**
- Overbuild: sem motor próprio (é Hermes), sem store canônico, sem React até precisar. **pass**
- Navegação: L0 é o "primeiro executável"; tudo depende dele. **pass**

## Blocker / gap ledger
- **G-1 (dep):** Hermes de pé (RUNBOOK 0–6) antes de L1. Ponte até lá: Telegram/Claude Code.
- **G-2 (resolvido):** stack = **Django + HTMX + Tailwind** (a teu pedido). FastAPI/React ficam como alternativas.
- **G-3 (owner):** segredos/keys (Hermes key, e no Hermes: ClickUp token, GitHub PAT, model key), VPS, domínio/Tailscale.
- **G-4 (design):** modelo de recência "última vez que fiz" por tipo de task (recorrente vs campo) — fechar no setup do ClickUp (RUNBOOK 0a).

## Next route
`task-session` por onda, começando por **L0 (T-A0…T-A3)** — mas só depois do Hermes de pé.
Enquanto isso, ler pela ponte. Recomendo eu **scaffoldar o L0** quando você disser "constrói".

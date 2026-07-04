---
artifact: work-pack
capability: escritorio-app
authored_by: invoke/plan
status: baseline
complexity: high
output_mode: single-file
source_refs: [APP-ARCHITECTURE.md, CAPTURE-GRAMMAR-SPEC.md, REMINDER-SKILL-SPEC.md, RUNBOOK.md]
implements: D-12 (Expo/RN), D-13 (BFF FastAPI), D-14 (push FCM + Telegram)
supersedes: baseline anterior deste arquivo (Django+HTMX+PWA)
---

# APP-WORK-PACK — cockpit nativo (Expo + BFF)

**Objetivo:** construir o cockpit pessoal — **app Android nativo (Expo/React Native)** + **BFF fino
(FastAPI)** — como vidro sobre o Hermes: captura (leitura #1 + tarefas/notas), consulta (tarefas por
área) e **push no app** (nudge). No VPS.

**Dispatch trace:** `sequence` (Hermes → BFF → app), `scu_swu_reduction` (cada tarefa = unidade
mínima), `recomposition_proof` (tarefas remontam nas telas + push do APP-ARCHITECTURE),
`validation_loop` (cada onda tem "prove it"), `owner_boundary_check` (invoke planeja; owner/agente
executa), `residue_ledger` (deps e gaps visíveis), `execution_receipt_handoff` (passos live nomeiam o dono).

## Dependência dura (com atalho)
O app é vidro sobre o Hermes (RUNBOOK estágios 1–5: VPS, Hermes, modelo+Telegram, MCP ClickUp+GitHub,
profiles, skill de lembrete). **MAS L0 e boa parte do L1 dão pra construir contra um Hermes mockado,
local, sem esperar o VPS** — plugar o Hermes real é trocar a URL base. Assim dá pra **começar já** e o
engine subir em paralelo. Até o app chegar em L1 real, **ler/cobrar pela ponte** (Telegram).

## Ondas por camada (L0→L3)

### L0 — encanamento (app ↔ BFF ↔ Hermes) + push
Pergunta: o app manda texto pro BFF, vira coisa no vault, e uma notificação chega no celular?
- **T-A0** Scaffold: repo com `app/` (Expo/React Native) + `bff/` (FastAPI). BFF roda local; app roda
  no teu Android via **Expo Go**.
- **T-A1** Auth single-user no BFF (login → token de sessão); app guarda no **SecureStore**.
- **T-A2** BFF `POST /capture` → repassa texto pro Hermes (profile Leitura); `HERMES_API_KEY` no env
  do BFF. (Contra **mock do Hermes** primeiro.)
- **T-A3** App: tela mínima — caixa de texto + enviar + área de resposta.
- **T-A4** **Push plumbing:** app pega o **Expo push token** → `POST /devices`; BFF
  `POST /internal/notify` → dispara push via **Expo Push Service**; um push de teste chega no celular.
- **Prove it:** logar no app → digitar nota → BFF→Hermes→vault (real quando Hermes existir; mock
  antes) e app mostra "✅"; **e** um push de teste aparece no Android. *(desbloqueia tudo)*

### L1 — valor diário (o que você usa todo dia)
- **T-A5** Tela **Tarefas**: por área (Trabalho/Finanças/Saúde/Pessoal) + recência ("última vez há
  X"); criar/concluir. Via BFF → Hermes → ClickUp MCP.
- **T-A6** Tela **Capturar-Leitura**: seletor de profile, sessão (livro abre, falas anexam,
  "compilar" finaliza), mostra itens da sessão. Usa a CAPTURE-GRAMMAR (6 modos) no Hermes.
- **T-A7** **Push real do nudge:** cron `reminder-digest` do Hermes → Telegram **e**
  `POST /internal/notify` → FCM → app. Tocar a notificação abre a tela **Tarefas**.
- **T-A8** Erros/timeout (Hermes fora → mensagem clara, sem travar).
- **Prove it:** "me mostra Saúde" lista com recência; criar tarefa aparece no ClickUp; o digest da
  manhã chega **como push no app E no Telegram**.

### L2 — cockpit redondo
- **T-A9** Tela **Chat** (conversa por profile) via `/v1` do Hermes (proxy do BFF).
- **T-A10** Tela **Revisão**: digest do dia + itens ★ pra Anki.
- **T-A11** Polish mobile-first + **deep-link** da notificação (abre a tela certa) + hardening de auth.
- **Prove it:** usar captura, consulta e chat pelo celular; a notificação abre a tela correta.

### L3 — rodar sozinho
- **T-A12** Deploy: BFF no VPS (Caddy HTTPS, systemd), Hermes ao lado; build do app (**EAS build** →
  APK / canal interno da Play).
- **T-A13** Runbook de operação (subir/atualizar/rollback; renovar credencial FCM/token do Hermes).
- **Prove it:** reinicia o VPS → BFF + Hermes sobem sozinhos; app instalado funciona fora de casa;
  push chega.

## SWUs (núcleo)
- **SWU-APP-001** (T-A2): BFF proxy `POST /capture` → Hermes. Aceite: texto entra, nota sai no vault.
  Write: `bff/app/capture.py`, `bff/app/hermes_client.py`. Verify: request autenticado → commit no vault.
- **SWU-APP-002** (T-A4/T-A7): **push relay**. `POST /devices` + `POST /internal/notify` → fan-out FCM.
  Write: `bff/app/devices.py`, `bff/app/push.py` (POST pro **Expo Push API** via httpx); app: registro
  do token (`expo-notifications`). Aceite: digest do Hermes vira push no Android.
- **SWU-APP-003** (T-A5): tarefas por área + recência via Hermes→ClickUp. Aceite: lista agrupada por
  Space, "última vez" correta; criar/concluir reflete no ClickUp. Write: `app/screens/Tasks.tsx` + proxy.
- **SWU-APP-004** (T-A1): auth single-user + segredos server-side. Aceite: sem token → 401; a chave do
  Hermes nunca no app. Write: `bff/app/auth.py`, `app/lib/session.ts`.

## Estratégia de validação
- L0/L1: BFF testável com o Hermes **mockado** (pytest, sem rede); app testável com o BFF mockado; +
  um "prove it" manual por onda contra o real.
- Segurança: teste que `HERMES_API_KEY` / credencial FCM nunca aparecem em resposta; rota sem token = 401.
- Push: teste de `/internal/notify` → chamada FCM (mock do firebase-admin); aceite vivo = push real no
  teu Android.

## Distill
- Unidade mínima: cada tarefa toca uma tela ou uma rota do BFF. **pass**
- Recomposição: tarefas remontam nas 4 telas + push do APP-ARCHITECTURE. **pass**
- Overbuild: sem motor próprio (é Hermes), sem store canônico; o BFF é só proxy+auth+push. **pass**
- Navegação: L0 (incl. push plumbing) é o "primeiro executável"; tudo depende dele. **pass**

## Blocker / gap ledger
- **G-1 (dep):** Hermes de pé (RUNBOOK 1–5) pro L1 real; **L0 roda contra mock**. Ponte até lá: Telegram.
- **G-2 (resolvido):** stack = **Expo/RN (app) + FastAPI (BFF)** (D-12/D-13) — supersede Django+HTMX+PWA.
- **G-3 (owner):** keys — `HERMES_API_KEY`; push via **Expo Push Service** (EAS gerencia o FCM; sem
  service account no BFF); e no Hermes: ClickUp token, GitHub PAT, model key; VPS, domínio.
- **G-4 (design):** recência "última vez que fiz" por tipo de task (recorrente vs campo) — fechar no
  setup do ClickUp (RUNBOOK 0a).
- **G-5 (novo):** **dev build (EAS)** pro push remoto funcionar no Android (Expo Go atual não recebe
  push); FCM gerenciado pela Expo/EAS — sem service account no BFF.

## Next route
`task-session` por onda, começando por **L0 (T-A0…T-A4)** — **construível já, contra um Hermes
mockado**, sem esperar o VPS. Em paralelo: rodar o **Stage 0** do RUNBOOK (fontes + keys) e subir o
Hermes (stages 1–5). Recomendo eu **scaffoldar o L0** (app Expo + BFF FastAPI + push de teste) quando
você disser "constrói".

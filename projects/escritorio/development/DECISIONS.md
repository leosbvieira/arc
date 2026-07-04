---
artifact: decision-log
capability: escritorio
status: baseline
---

# DECISIONS — escritório

Every locked decision with its rationale, so nobody (including a future Claude) "improves"
it in the wrong direction. Ordered roughly by how load-bearing it is.

| # | Decision | Rationale | Consequence |
|---|---|---|---|
| **D-1** | **Glass, not store.** The escritório holds no canonical data; everything round-trips to ClickUp / the vault. | The whole failure mode Leo repeats is "new input place → dies in 2 weeks / scatters more". The cure for scatter is electing ONE home per thing, not adding another. | Every feature must read from / write to an existing source. A local DB is only allowed for *scaffolding state* (dedupe, cache), never task/note content. |
| **D-2** | **ClickUp = single home for ALL tasks**, 1 Space **escritório** + **1 List (folderless) por área** — Trabalho, Finanças, Saúde, Pessoal (refinado 2026-07-01: List em vez de Space por área — a API de tasks do ClickUp é por List e casa com o cliente list-based do cutuca). TickTick retired for tasks. | To answer "me mostra Saúde e a última vez que fiz", tasks must live in one place with a real API and recency/recurrence. ClickUp has the API; TickTick is capped. | Migrate personal/health tasks into ClickUp Lists (uma por área). The reminder + task-manager view read one source (o BFF mapeia área→list_id). |
| **D-3** | **Obsidian vault lives in a GitHub repo.** | Obsidian is local markdown with no cloud API — the worst connector. GitHub gives it a real remote (git + GitHub API + an existing GitHub MCP) and kills the Obsidian-Sync requirement. | Notes read/write = the GitHub MCP. The mini-server only needs git/GitHub access, not the vault on disk. |
| **D-4** | **Engine = Hermes Agent** (self-hosted). | Covers reach (Telegram) + memory/skills + built-in cron + MCP tools + an API server that fronts any cockpit — one piece where LibreChat would need 3–4 bolted together. | Adopt, don't build the engine. Build only: MCP wiring, profiles, the cadence skill, config. |
| **D-5** | **Model auth = API keys** (or a router / Nous Portal). Subscription OAuth **only** in the real `claude`/`claude -p` binary for batch. | Feb-2026 ToS wall: subscription OAuth in any non-official client is blocked server-side (Anthropic) or simply doesn't exist (ChatGPT Plus has no API). Hermes uses API keys → compliant; it's the legit OpenClaw successor. | Put an Anthropic/OpenAI/router key (with spend cap) in the mini-server env. Never a subscription token in the app. |
| **D-6** | **Surface = Telegram + web cockpit, one engine.** Cockpit path: Hermes dashboard → Open WebUI/LobeChat → own app. | Leo wanted a "cockpit he lives in" but is forgetful — a place he must remember to open dies. Hermes gives *both*: Telegram reaches him; the cockpit (glass over Hermes' API) is for consulting. No either/or. | Build order defers the custom cockpit to last (plumbing → adopt cockpit → own UI). |
| **D-7** | **Reminders = digest + tone escalation, config-driven. No interval spam.** | "Every X minutes/hours" is alarm fatigue; dies in a week. Persistence without spam: reappears daily until killed, firmer as it ages. | Encode `cutuca`'s cadence rules as a Hermes cron skill. Cadence values are config, not hardcode. |
| **D-8** | **Profiles ≈ "multiple agents".** | Hermes is one learning agent with selectable profiles, not N separate agents. Profiles (Tarefas, Notas) recover the multi-agent feel; one assistant that knows the whole life is more coherent. | Configure a profile per lane instead of standing up separate agent apps. |
| **D-9** | **Host = a $5–10/mo VPS** (always-on). | Vault-on-GitHub (D-3) removed the only reason to keep the host at home; a VPS is always-on, isolated from ConsigVerse, has easy HTTPS/domain, and Hermes runs on a $5 VPS with no GPU. | One VPS runs Hermes + the Django app + cron + the `claude -p` batch (headless OAuth token, renewed periodically). A home mini-server stays a valid alternative if you want fully local. |
| **D-10** | **cutuca runtime superseded; its rules promoted to spec.** | Hermes' cron + ClickUp MCP do what cutuca's cron did. But cutuca's cadence logic is validated (50 tests) and reusable. | cutuca stays as the cadence/requirements reference for the Hermes reminder skill; it stops running as a separate service. |
| **D-11** | **Custom app = primary capture + consult surface** (Leo's call, 2026-06-30). It is *glass over Hermes* — sends text to the API server, never runs the LLM or writes the vault itself. Daily reading capture routes through it. | It's where Leo wants to operate; keeping it thin over Hermes preserves D-1 (glass-not-store) and keeps one engine. | The app rises from "last/optional" to the primary surface. To not gate the daily reading habit on app-build, **bridge with the Telegram lane now**; switching surface later is swapping glass (same engine + vault) → zero rework. Reading is lane #1; see CAPTURE-GRAMMAR-SPEC.md. |
| **D-12** | **Cockpit = app nativo Expo/React Native (Android primeiro), não PWA.** (Leo, este ciclo.) Supersede a stack Django+HTMX+PWA que o app tinha sob D-11. | Leo quer um app "de verdade" na home, com push confiável *dentro* do app. Escolheu Android-only → FCM cobre o push nativo; e o Telegram segue como backbone de aviso. | O app vira um **cliente** — não pode guardar a chave do Hermes. Exige um BFF fino no VPS (D-13). Reescreve APP-ARCHITECTURE / APP-WORK-PACK pra RN. iPhone fica pra depois (mesmo código). |
| **D-13** | **BFF fino (FastAPI, Python) entre o app e o Hermes**, no VPS. | Um cliente nativo não pode embutir `HERMES_API_KEY` (extraível do APK); o segredo tem que morar num servidor. O BFF guarda o segredo, faz auth single-user, proxy pro Hermes, e é o **relay de push**. | Python (teu forte); leve (só JSON — sem templates/admin). Glass-not-store mantido: BFF só guarda auth/sessão + tokens de device FCM — nunca task/nota. Alternativa: Node/Express (mesma linguagem do app). |
| **D-14** | **Push dentro do app (FCM), além do Telegram; Telegram é o canal #1, WhatsApp depois.** | Leo quer notificação no app também. Telegram é push nativo à prova de bala e já decidido (D-6) — é o backbone; o FCM no app é a camada extra. WhatsApp (mais frágil) entra quando o gateway do Hermes estiver provado. | O digest tem **uma** fonte (skill `reminder-digest` no Hermes). O cron entrega no Telegram **e** faz `POST /internal/notify` no BFF, que faz fan-out FCM. Sem duplicar a cadência. |

## Explicitly deferred (not v1)
- **Email/Outlook** (MS Graph OAuth — the friction; phase 2).
- **WhatsApp as a channel** (Business API + templates + cost; Telegram first).
- **Voice capture** (Telegram audio → transcription → same pipeline; easy later).
- **Custom cockpit app** — *promoted* to the primary capture+consult surface (D-11) and agora é a
  entrega ativa: **app nativo Expo/React Native (Android) + BFF FastAPI** (D-12/D-13), não mais um
  PWA "por último". Ainda é vidro sobre um engine provado — dá pra construir app+BFF em paralelo
  contra um Hermes mockado e plugar o real quando os stages 1–5 do RUNBOOK subirem. Telegram é a
  ponte/backbone enquanto isso.
- **Hermes local/offline models (e.g., Hermes/Nous open weights)** — only worth it with a GPU
  box or if volume explodes; today API/router is cheaper-effort and more reliable.

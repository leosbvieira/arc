# RUNBOOK — building the escritório on the mini-server

Ordered **plumbing-first**: sources → engine → tools → reminders → cockpit last. Each stage
ends with a **Prove it** check — don't advance until it passes. Stages 1–3 are cheap and
reversible: that's the *prove-before-invest* gate on Hermes' maturity.

> Hermes is ~4 months old — commands/flags move. Treat the snippets as shape; confirm against
> the live docs (linked per stage). If Hermes fights you past stage 3, the **fallback** is
> LibreChat (cockpit) + the existing `../cutuca` (reminder cron) — same sources, same decisions.

> **Secrets rule:** every token lives in the mini-server's environment / secrets store, never in
> a repo, never pasted in chat. Put a **spend cap** on every model key.

---

## Stage 0 — Prepare the sources (no server yet)

**0a. ClickUp — one home, by life-area.**
- Create 4 Spaces (or Lists): **Trabalho, Finanças, Saúde, Pessoal**.
- Decide the recency model per area (DISCOVERY U-3): recurring tasks (completion date = "última
  vez") for habits/health; or a `feito em` custom field for one-offs.
- Get a **personal API token** (ClickUp → Settings → Apps). Note the Space/List IDs.
- Start moving personal/health tasks out of TickTick into the right Space (can be gradual).

**0b. Obsidian vault → GitHub.**
- `git init` the vault folder, push to a **private** GitHub repo.
- Create a **fine-grained PAT** scoped to *only that repo*, Contents read/write.

**0c. Keys.**
- Model access: an Anthropic and/or OpenAI API key, **or** a router key (OpenRouter/Requesty/
  Nous Portal). Set a spend cap.
- Telegram bot: @BotFather → `/newbot` → bot token.

**Prove it:** you hold — ClickUp token + Space IDs · GitHub repo URL + PAT · model key · bot token.
Nothing is in a repo or a chat.

---

## Stage 1 — Stand up the mini-server + Hermes

- Provision a small always-on Linux box (a $5–10 VPS is enough; no GPU). Keep it **isolated from
  ConsigVerse**.
- Install Hermes (single `curl`, per docs) — it bundles its own Python/Node/etc.
  Docs: https://github.com/nousresearch/hermes-agent
- Launch the CLI/TUI once.

**Prove it:** `hermes` starts, you get an interactive reply from the agent locally.

---

## Stage 2 — Model + Telegram (the reach)

- Configure the model provider: API key or router endpoint. Confirm the spend cap is live.
- Connect the **Telegram gateway** with the bot token; `/start` the bot from your phone.

**Prove it:** you message the bot on Telegram and it answers. It reaches *you*, on the app your
head already lives in.

---

## Stage 3 — Tools via MCP (retrieve + write) ← the real work

- Add the **ClickUp MCP** (read/write tasks). (A ClickUp MCP already exists — reuse it.)
- Add the **GitHub MCP** (read/write files in the vault repo), using the PAT.
  MCP registry: https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
- Grant only what's needed (least privilege on both).

**Prove it (the make-or-break test):**
- "liste minhas tasks de Saúde" → returns the ClickUp Space.
- "cria em Trabalho: cobrar Ana relatório, sexta" → task appears in ClickUp.
- "anexa em `Leituras/Sapiens.md`: cap 3 fraco" → commit shows in the vault repo.

> If Stage 3 passes, Hermes is genuinely 90% of the escritório. If it's painful here, stop and
> switch to the fallback — don't push uphill.

---

## Stage 4 — Profiles (your "agents")

- **Profile `Tarefas`** — task lane: cadence-aware, ClickUp-focused, knows the 4 Spaces.
- **Profile `Notas`** — vault lane: append/retrieve notes, book comments.

**Prove it:** switching profile changes behavior/tooling; `/v1/models` lists them (matters for the
cockpit later).

---

## Stage 5 — Reminder skill (port cutuca's rules)

Encode the validated cadence as a Hermes **cron** skill:
- **Rule** (from `../cutuca/src/cutuca/cadence.py`): chase if due-today OR overdue OR untouched ≥ N
  days; skip closed. Config values, not hardcode.
- **Dedupe:** don't repeat the same task the same day (scaffolding state is fine — that's not
  canonical data, so it doesn't break glass-not-store).
- **Tone escalation:** firmer as days-overdue grows.
- **Schedule:** morning digest (08:00); optional midday for overdue.
  Cron docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard

**Prove it:** run the digest twice in one day → each task chased once (dedupe), tone escalates with
lateness, delivered to your Telegram.

---

## Stage 6 — End-of-day batch (need #5)

- Hermes cron task, natural language: "fechamento do dia — releia tasks por área + notas do dia,
  consolide o que mudou, proponha o que revisar amanhã."

**Prove it:** an evening message summarizing the day and proposing tomorrow's focus.

---

## Stage 7 — Cockpit (glass, adopt first)

- Turn on Hermes' **API server**: `API_SERVER_ENABLED=true` + `API_SERVER_KEY`.
- Fastest: enable the **built-in Web Dashboard**. Or point **Open WebUI / LobeChat** at the API
  server (it speaks OpenAI-compatible `/v1`).
  Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/open-webui

**Prove it:** a browser cockpit where you pick a profile, chat, see history, and ask "me mostra
Saúde" with recency. Heads-up: dashboard WebSocket auth has open bugs — if it's flaky, use Open
WebUI instead.

---

## Stage 8 — O app nativo (agora **prioridade**, não "por último")

**Supersede:** o cockpit deixou de ser "web app por último". Agora é um **app Android nativo
(Expo/React Native) + um BFF fino (FastAPI)** no VPS — ver `development/APP-ARCHITECTURE.md` e
`development/APP-WORK-PACK.md` (D-12/D-13/D-14). O Stage 7 (Open WebUI/dashboard) vira só um
atalho opcional pra ter *algum* cockpit web enquanto o app nativo não está pronto.

- O app é vidro sobre o Hermes; o **BFF** guarda a `HERMES_API_KEY`, faz auth single-user, proxy
  pro Hermes e o **relay de push (FCM)**.
- Dá pra **construir app + BFF em paralelo** contra um Hermes **mockado** (local, sem VPS) e plugar
  o Hermes real quando os stages 1–5 estiverem de pé.
- Push no app: cron `reminder-digest` do Hermes → Telegram **e** `POST /internal/notify` no BFF →
  FCM → celular. Telegram segue como backbone.

O plano em ondas (L0→L3) está em `development/APP-WORK-PACK.md`. Push via **Expo Push Service**
(EAS gerencia o FCM); precisa de um **dev build** pra receber push no Android — Expo Go atual não
recebe push remoto.

---

## Deferred (not now)
Email/Outlook (MS Graph OAuth), WhatsApp channel, voice capture, local/GPU models. All plug into
the same engine later — see DECISIONS.md.

## Owner checklist before Stage 1
- [ ] ClickUp: 4 Spaces + personal token + Space IDs
- [ ] GitHub: vault repo (private) + fine-grained PAT
- [ ] Model key (or router key) + spend cap
- [ ] Telegram bot token
- [ ] A mini-server (or PC-on) reachable and isolated from ConsigVerse

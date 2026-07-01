---
artifact: architecture-bundle
capability: escritorio
profile: domainspec-architecture
status: baseline
source_refs: [DISCOVERY.md, DECISIONS.md]
---

# ARCHITECTURE — escritório (Escritório sobre Hermes)

## View 1 — Context

```
   ┌────────┐  texto/voz + perguntas   ┌──────────────────────┐
   │  Leo   │ ───────────────────────▶ │   escritório          │
   │        │ ◀─────────────────────── │  (Hermes no mini-srv) │
   └────────┘  digest, respostas       └───────┬──────────────┘
        ▲  cockpit web (consulta)               │ MCP
        │                          ┌────────────┼─────────────┐
   ┌────┴─────┐               ┌────▼────┐  ┌─────▼──────┐  ┌───▼────┐
   │ cockpit  │               │ ClickUp │  │ GitHub     │  │ router │
   │ (glass)  │               │ (tasks  │  │ vault      │  │ /LLM   │
   └──────────┘               │ p/ área)│  │ (Obsidian) │  │ (API)  │
                              └─────────┘  └────────────┘  └────────┘
```

External: LLM provider(s) via router/API key; ClickUp; GitHub (vault); Telegram.
Local (mini-server): Hermes engine + its memory/skills/cron + scaffolding state.

## View 2 — High-level structure (layers)

```
COCKPIT (glass)   Hermes dashboard → Open WebUI/LobeChat → seu app próprio
      │  REST /api/sessions/*, OpenAI-compatible /v1, WebSocket   (API_SERVER_KEY)
ENGINE            Hermes Agent  — profiles, memory/skills, cron, gateway
      │  MCP  +  model calls (API key / router)
TOOLS (MCP)       ClickUp MCP  ·  GitHub MCP  ·  (Outlook MCP = fase 2)
      │
SOURCES (store)   ClickUp Spaces: Trabalho·Finanças·Saúde·Pessoal   +   vault repo
```

## View 3 — Components

| Component | Role | Build vs Adopt |
|---|---|---|
| Hermes engine | Brain: chat, profiles, memory, skills, cron, messaging gateway, API server. | **Adopt** |
| Model access | Claude/GPT/… via API key or a router (OpenRouter/Requesty/Nous Portal), spend cap. | **Adopt/config** |
| ClickUp MCP | Read/write tasks by Space (life-area); recency/recurrence. | **Adopt** (exists) |
| GitHub MCP | Read/write markdown in the vault repo. | **Adopt** (exists) |
| Profile: *Tarefas* | Cadence-aware task lane (cobrança + criar + "me mostra área X"). | **Config** |
| Profile: *Notas* | Vault lane (append/retrieve notes, book comments). | **Config** |
| Reminder skill | Morning digest: due/overdue/stale, dedupe, tone escalation. Hermes cron. | **Build (small)** — port cutuca rules |
| End-of-day batch | Cron: re-read tasks+vault, consolidate, propose. | **Build (small)** — a Hermes cron task/skill |
| Cockpit | Web glass over Hermes' API. | **Adopt** now / **Build** later |
| cutuca | Cadence spec + fallback runtime. | **Reference** |

## View 4 — Workflows

**Capture (event):** Leo texts Telegram → Hermes (profile Tarefas) parses → ClickUp MCP
creates task in the right Space → replies "✅ …". Notes → profile Notas → GitHub MCP append.

**Consult (pull):** "me mostra Saúde" → Hermes reads ClickUp Space Saúde via MCP →
returns tasks + recency ("Dentista — última vez há 7 meses…"). Same in the cockpit.

**Remind (cron/push):** morning Hermes cron → read ClickUp → cadence filter (due/overdue/
stale) → dedupe → tone-escalated digest → Telegram. No interval spam.

**Batch (cron):** end-of-day Hermes cron → re-read tasks + vault → consolidate/propose.

## View 5 — Decision flow (auth, the sharp edge)

```
model call needed?
   ├─ in the escritório (Hermes/cockpit)  → API key / router   (NEVER subscription OAuth)
   └─ heavy batch on Leo's own machine    → real `claude`/`claude -p`  → OAuth OK
data to store?
   └─ ALWAYS → ClickUp (task) or GitHub vault (note).  Local DB only for dedupe/cache.
```

## View 6 — Dependency / interface map

- **Hermes API server:** `API_SERVER_ENABLED=true` + `API_SERVER_KEY`; REST `/api/sessions/*`,
  `/v1/models|skills|toolsets` (OpenAI-compatible), WebSocket `/api/pty?profile=`. → the cockpit's contract.
- **ClickUp:** personal API token; Spaces/Lists = life-areas; due_date, date_updated, recurring = recency.
- **GitHub vault:** private repo + fine-grained PAT (contents R/W on that repo).
- **Telegram:** bot token (BotFather) → Hermes gateway; owner chat_id.
- **Secrets:** all in mini-server env / secrets store, never in repo. Spend caps on model keys.

**Risks:** Hermes maturity (~4mo; open dashboard/WebSocket bugs) → prove-before-invest, fallback
LibreChat+cutuca. ClickUp assignee/name resolution tuned live. GitHub MCP write scope kept minimal.

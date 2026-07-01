---
artifact: spec
capability: cutuca
authored_by: invoke/define
discovery_waiver_reason: >
  Source is a complete, decision-closed build brief supplied by the owner.
  The brief serves as discovery + define input; --skip-discovery waiver recorded.
status: baseline
---

# SPEC — cutuca

## 1. One-liner

A thin **capture-and-nudge layer over ClickUp**, operated by a single owner (Leo)
through Telegram. It funnels tasks *in* (Telegram message → ClickUp task) and nudges
the owner *out* (a daily digest of what needs chasing). ClickUp is the single source
of truth. **cutuca is not** an app, a UI, or a new task database.

## 2. Actors

| Actor | Role | In v0? |
|---|---|---|
| Owner (Leo) | Sends tasks, receives all nudges | Yes |
| Employees (assignees) | Referenced as ClickUp assignees on tasks | Named only |
| Employees as bot users | Interact with the bot directly | **No** (Fase 2+) |

Only the owner ever receives a notification. The goal is to help the owner remember
to chase employees — not to notify employees.

## 3. Scope

### In scope (v0)
- **Flow A — Capture (event-driven):** Telegram text message → LLM parse → ClickUp
  task creation → Telegram confirmation.
- **Flow B — Nudge (scheduled):** cron digest reading ClickUp tasks, cadence-filtered
  and de-duplicated, sent to the owner only. Pure code, **no LLM**.
- Ask-back on ambiguous/incomplete capture instead of creating a garbage task.
- Config-driven cadence and ClickUp target list.
- Structured logging of what was created and what was nudged.

### Out of scope (v0) — deliberate
- Voice message capture (deferred; plugs into the same `parse_task`).
- WhatsApp / any second channel (isolated behind one send function for later).
- Outlook / MS Graph ingestion (OAuth friction; owner redirects manually for now).
- Employee-facing interactions.
- Any UI, dashboard, or task store outside ClickUp.
- Serverless deployment (documented as the Fase-2 alternative; v0 is long-poll).

## 4. Closed decisions (rationale preserved)

| Decision | Choice | Why |
|---|---|---|
| Source of truth | ClickUp | Cure for "scattered" is electing ONE home, not adding a third. Task-to-person has assignee/due/status = ClickUp shape. |
| Capture model | Event-driven | Parse happens at send time with instant confirmation. No polling. |
| Nudge model | Digest + persistence | "Every X min" = alarm fatigue; dies in a week. Persist without spam; tone escalates with lateness. Cadence is config, not hardcode. |
| Channel (v0) | Telegram | BotFather, free, trivial proactive push. WhatsApp proactive needs Business API + approved templates + per-message cost. |
| LLM | Messages API + Haiku (`claude-haiku-4-5-20251001`) | "Sentence → JSON" is pure transformation. No harness/Agent SDK/MCP needed. Haiku is faster and costs cents/month. |
| Listener (v0) | Long-poll process + SQLite | Brief's own "simplest" pick. Serverless (webhook/Lambda/DynamoDB) is the documented Fase-2 path. |
| LLM footprint | Flow A only | Flow B is pure code (read ClickUp, filter, format). Keep it LLM-free in v0. |

## 5. Functional requirements

- **FR-1** Owner sends free-text task in Telegram → bot replies with a structured
  confirmation and a ClickUp task exists (assignee, due date, status open).
- **FR-2** If the parse is incomplete/ambiguous (missing assignee or due date), the
  bot **asks back** ("pra quem? qual prazo?") instead of creating a task.
- **FR-3** The parser is isolated behind `parse_task(text) -> {assignee, titulo,
  prazo_iso, lista}` and returns strict JSON; malformed model output never creates a task.
- **FR-4** A scheduled digest (configurable times, default 08:00) reads ClickUp tasks
  in the target list and selects those matching the cadence rule
  (`vence_em_dias`, `atrasada`, `sem_update_dias`).
- **FR-5** The digest de-duplicates: a task already nudged today is not repeated
  identically; tone escalates with days overdue when `escala_tom` is on.
- **FR-6** Digest is delivered to the owner's chat only.
- **FR-7** All secrets come from env/`.env`; none are hardcoded.
- **FR-8** Sending is isolated behind one channel function so swapping channel changes
  only that function.

## 6. Non-functional requirements

- **NFR-1 Cost guard:** the Anthropic key carries a console-side spend limit; Haiku only.
- **NFR-2 Fail safe:** parse/network failures degrade to an ask-back or a logged skip,
  never a corrupt ClickUp task or a crash of the digest.
- **NFR-3 Idempotent nudges:** re-running the digest on the same day produces no dupes.
- **NFR-4 Swappable channel & model:** channel and model each sit behind one seam.
- **NFR-5 Portable state:** dedupe state is a single local SQLite file (swappable for
  DynamoDB in the serverless path).

## 7. External inputs (owner-supplied, never in code)

1. `ANTHROPIC_API_KEY` — console.anthropic.com → API keys (set spend limit).
2. `TELEGRAM_BOT_TOKEN` — @BotFather `/newbot`; owner then `/start`s the bot so it
   learns the owner `chat_id`.
3. `CLICKUP_TOKEN` — ClickUp → Settings → Apps → API Token.
4. `clickup_list_id` — the employee-tasks list.
5. Cadence values in `config.yaml` (tunable while running).

## 8. Acceptance (v0 done)

- Sending a normal task in Telegram creates the right ClickUp task and returns a
  confirmation, verified against a real list.
- An ambiguous message triggers an ask-back, not a task.
- The digest, run twice in one day, chases the correct tasks once (no dupes) with
  escalating tone for overdue items.
- No secret appears in the repo; `config.yaml` and `.env` are gitignored.

See [GLOSSARY.md](./GLOSSARY.md) for terms and [ARCHITECTURE.md](./ARCHITECTURE.md) for design.

---
artifact: architecture-bundle
capability: cutuca
authored_by: invoke/design
profile: domainspec-architecture
status: baseline
source_refs: [SPEC.md, GLOSSARY.md]
---

# ARCHITECTURE — cutuca

Six-view design bundle. Non-mutating: upstream corrections are gap-ledger entries, not silent edits.

---

## View 1 — Context

```
        ┌──────────────┐   text task    ┌──────────────┐
        │   Owner      │ ─────────────▶ │              │
        │  (Telegram)  │ ◀───────────── │    cutuca    │
        └──────────────┘  confirm/nudge │   (v0 host)  │
                                        └──────┬───────┘
                     parse (1 HTTP call)       │      read/write tasks
                 ┌──────────────────────┐      │   ┌──────────────────┐
                 │ Anthropic Messages    │◀─────┼──▶│  ClickUp API v2   │
                 │ API (Haiku)           │      │   │ (source of truth) │
                 └──────────────────────┘      │   └──────────────────┘
                                        ┌───────┴────────┐
                                        │ SQLite (dedupe │
                                        │ nudge state)   │
                                        └────────────────┘
```

External systems: Telegram (channel), Anthropic Messages API (parse, Flow A only),
ClickUp API v2 (source of truth). Local: SQLite (nudge dedupe state).

---

## View 2 — High-level structure

Two independent flows over shared clients:

```
FLOW A (capture, event-driven)          FLOW B (nudge, scheduled)
telegram_channel (long-poll)            scheduler (APScheduler)
      │ on message                            │ at digest_horarios
      ▼                                        ▼
   capture.handle()                        nudge.run_digest()
      │  parse_task() ─▶ Anthropic            │  clickup.list_tasks()
      │  clickup.create_task()                │  cadence.select() (pure)
      ▼                                        │  state.filter_new() (SQLite)
   telegram_channel.send(confirm)             │  format digest
                                              ▼
                                         telegram_channel.send(digest)
```

Shared building blocks: `config`, `logging_setup`, `clickup` client,
`telegram_channel` (the swappable send seam), `state` (SQLite).

---

## View 3 — Low-level components

| Module | Responsibility | Depends on | LLM? |
|---|---|---|---|
| `config.py` | Load `config.yaml` + env secrets into typed objects; fail loud on missing required. | pyyaml, os | no |
| `logging_setup.py` | Structured JSON-ish logging (created/nudged/errors). | stdlib logging | no |
| `parser.py` | `parse_task(text, client=None)` → strict-JSON dict; ask-back sentinel on failure. | anthropic (lazy, injectable) | **yes** |
| `clickup.py` | `create_task()`, `list_tasks()`; REST v2, timeouts, retries. | requests | no |
| `cadence.py` | Pure rules: `needs_nudge(task, rule, today)` + `tone(days_overdue)`. | stdlib | no |
| `state.py` | SQLite dedupe: `already_nudged()`, `mark_nudged()`. | sqlite3 | no |
| `telegram_channel.py` | `send(chat_id, text)` + long-poll wiring. The channel seam. | python-telegram-bot (lazy) | no |
| `capture.py` | Flow A orchestration: message → parse → create → confirm / ask-back. | parser, clickup, telegram | indirect |
| `nudge.py` | Flow B orchestration: read → select → dedupe → format → send. | clickup, cadence, state, telegram | no |
| `app.py` / `__main__` | Wire long-poll handlers + scheduler; boot. | all | no |

The two seams the brief demands: **model** behind `parse_task(...)`, **channel**
behind `telegram_channel.send(...)`.

---

## View 4 — Workflow process

**Flow A (capture):**
1. Owner sends text in Telegram.
2. `capture.handle()` calls `parse_task(text)`.
3. Parse OK & complete → `clickup.create_task()` → reply `✅ criei: <titulo> · <assignee> · vence <prazo>`.
4. Parse incomplete/malformed → reply ask-back; **no task created**.

**Flow B (nudge):**
1. Scheduler fires at a `digest_horarios` time.
2. `clickup.list_tasks(list_id)` fetches employee tasks.
3. `cadence.select(tasks, rule, today)` (pure) → tasks needing a chase.
4. `state.filter_new(selected, today)` drops already-nudged-today.
5. Format digest (tone per `escala_tom`) → `telegram_channel.send(owner_chat_id, digest)`.
6. `state.mark_nudged(task_ids, today)`.

---

## View 5 — Decision flow

```
message ──▶ parse_task
              │
    ┌─────────┴──────────┐
    ▼                    ▼
 valid JSON?          json.loads fails / missing field
    │ yes                │
    ▼                    ▼
 create task         ask-back (no write)
    │
    ▼
 confirm

digest tick ──▶ for each task: needs_nudge(rule)?
                   │ yes
                   ▼
              already_nudged_today?
                 ┌──┴──┐
                yes    no
                 │      ▼
                skip   include + escalate tone by days_overdue
                        ▼
                     send digest ▶ mark_nudged
```

---

## View 6 — Dependency / interface map

**Internal interfaces (contracts):**
- `parse_task(text: str, client=None) -> dict | None` — `None` means ask-back.
  Success dict: `{assignee: str|None, titulo: str, prazo_iso: str|None, lista: str|None}`.
- `clickup.create_task(list_id, title, assignee_ids, due_ts) -> Task`
- `clickup.list_tasks(list_id) -> list[Task]` where Task exposes
  `id, name, assignees, due_date, date_updated, status`.
- `cadence.needs_nudge(task, rule, today) -> bool` (pure)
- `cadence.tone(days_overdue: int) -> str` (pure)
- `state.already_nudged(task_id, day) -> bool` / `state.mark_nudged(task_id, day)`
- `channel.send(chat_id, text) -> None`

**External deps:** Anthropic Messages API (Haiku); ClickUp REST v2; Telegram Bot API.
All secrets injected via `config` from env. All network calls carry timeouts.

**Glossary consistency:** all View terms (Capture, Nudge, Digest, Cadence rule,
Dedupe, Tone escalation, parse_task, Ask-back, Channel, Target list) are defined in
GLOSSARY.md — status: **pass**.

---

## Design decisions & risks

| ID | Decision | Rationale | Risk / mitigation |
|---|---|---|---|
| D-1 | Lazy-import heavy libs (anthropic, telegram, apscheduler) inside functions. | Keeps pure-logic + parser testable with zero heavy deps; eases serverless split. | none material |
| D-2 | Dependency injection for the model client in `parse_task`. | Unit-test parsing without network or key. | none |
| D-3 | ClickUp `Task` is a thin dataclass adapter over raw JSON. | Isolates cadence logic from API shape drift. | API field rename → adapter is the single change point |
| D-4 | Dedupe key = `(task_id, YYYY-MM-DD)`. | Simplest correct idempotency for a daily digest. | multiple digests/day still dedupe within the day (intended) |
| D-5 | Tone escalation is a pure function of days-overdue buckets. | Deterministic, testable, no LLM. | wording tuned in config later |

**Next route:** `plan` → IMPLEMENTATION-LAYERING.md + WORK-PACK.md.

# cutuca

> **Status (2026-06-30):** the scope grew into a broader personal agent hub —
> see `../escritorio`. cutuca's *runtime* is superseded there by Hermes' cron + ClickUp MCP,
> but its **cadence rules** (this repo) are the validated spec for that reminder skill, and it
> stays as the working fallback. Everything below still runs and passes.

A thin **capture-and-nudge layer over ClickUp**, operated by one owner via Telegram.

- **Capture (Flow A):** you send a task in Telegram → Haiku parses it → a ClickUp task
  is created → you get a `✅ criei…` confirmation. On the spot, event-driven.
- **Nudge (Flow B):** a scheduled digest reads ClickUp, figures out what needs chasing
  today (due / overdue / stale), de-duplicates so it never spams, escalates tone with
  lateness, and messages **you** (only you).

ClickUp is the single source of truth. cutuca is **not** an app, a UI, or a new task
store. It is a funnel in and a nudge out.

> Full rationale and design live in [`development/`](./development): SPEC, GLOSSARY,
> ARCHITECTURE (six views), IMPLEMENTATION-LAYERING, WORK-PACK. These were authored via
> Arcanum `invoke` (define → design → plan).

---

## Architecture at a glance

```
FLOW A (capture, event-driven)          FLOW B (nudge, scheduled)
Telegram long-poll                       APScheduler cron (08:00, opt 13:00)
   → parse_task()  ── Haiku ──▶             → clickup.list_tasks()
   → clickup.create_task()                  → cadence.select()   (pure)
   → reply "✅ criei …"                      → state dedupe       (SQLite)
                                            → format + escalate tone
                                            → telegram send (owner only)
```

The LLM appears **only** in Flow A, behind one function (`parse_task`). The channel
sits behind one seam (`TelegramChannel.send`). Swapping model or channel touches only
that one place.

---

## Setup

### 1. Python env

This machine intercepts TLS (self-signed cert in chain), so pip needs trusted hosts:

```bash
cd projects/cutuca
python -m venv .venv
.venv/Scripts/python -m pip install \
  --trusted-host pypi.org --trusted-host files.pythonhosted.org \
  -r requirements.txt
.venv/Scripts/python -m pip install -e .      # so `python -m cutuca` resolves
```

(On a normal network drop the `--trusted-host` flags. On macOS/Linux the venv python is
`.venv/bin/python`.)

### 2. Secrets — in `.env`, never in code, never pasted in chat

```bash
cp .env.example .env      # then edit
```

| Var | Where | Note |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys | **Set a spend limit on the key** as a runaway guard. |
| `TELEGRAM_BOT_TOKEN` | @BotFather → `/newbot` | |
| `CLICKUP_TOKEN` | ClickUp → Settings → Apps → API Token | Personal token, starts `pk_`. |

### 3. Config — in `config.yaml` (gitignored)

```bash
cp config.example.yaml config.yaml   # then edit
```

Fill `clickup.list_id` (the employee-tasks list). Leave `owner_chat_id: null` for now.

### 4. Learn your chat_id

```bash
.venv/Scripts/python -m cutuca run
```

Open Telegram, `/start` your bot, send any message. The log prints
`"event":"owner_chat_id","chat_id":<N>`. Put `<N>` into `config.yaml` → `owner_chat_id`
and restart. Now the digest knows where to go.

---

## Running

```bash
python -m cutuca run       # v0 default: long-poll listener + digest scheduler (blocks)
python -m cutuca digest    # run one digest now and exit (cron / manual test)
python -m cutuca parse "joão manda o relatório sexta"   # test the parser alone (needs key)
```

### Keep it running (long-poll host)

- **Windows:** Task Scheduler → run `…\.venv\Scripts\python.exe -m cutuca run` at logon,
  "restart on failure".
- **Linux/VPS:** a `systemd` unit with `Restart=always`, or `pm2 start "python -m cutuca run"`.

Flow B is scheduled in-process by APScheduler, so the same running process handles both
flows. If you'd rather cron the digest externally, disable `digest_horarios` and run
`python -m cutuca digest` from OS cron.

---

## Testing

```bash
python -m pytest        # 50 tests, no network — all collaborators are faked/injected
```

Pure logic (cadence, dedupe, parser JSON, capture pipeline, digest) is fully covered.
Network clients are tested against mocked sessions and an injected fake model client.

**Live acceptance (owner-run, needs the 3 secrets + list_id):**
1. Send a normal task in Telegram → correct ClickUp task + `✅` confirmation.
2. Send an ambiguous one ("resolve isso") → bot asks back, no task created.
3. `python -m cutuca digest` twice in a day → each task chased once, tone escalates.

---

## Roadmap (deliberately out of v0)

- **Voice capture:** Telegram audio → transcription → same `parse_task`. Plugs into the
  existing seam.
- **WhatsApp channel:** a new `Channel` subclass with `.send()`; the rest is unchanged.
- **Outlook ingestion:** cron reads flagged mail via MS Graph; ClickUp stays canonical.
- **Serverless (Fase 2):** Telegram webhook → API Gateway → Lambda for Flow A;
  EventBridge cron → Lambda for Flow B; DynamoDB replaces SQLite (`state.py` is the only
  swap point). `run_digest_once` is already a clean Lambda handler seam.

---

## Layout

```
src/cutuca/
  config.py            config + secrets (secrets from env only)
  parser.py            parse_task — the ONE model seam (Haiku)
  clickup.py           ClickUp REST v2 client + raw→Task adapter
  cadence.py           pure nudge rules + tone escalation
  state.py             SQLite dedupe (task_id, day)
  telegram_channel.py  the ONE channel seam (send via Bot API)
  capture.py           Flow A pipeline (parse→create→confirm / ask-back)
  nudge.py             Flow B pipeline (read→select→dedupe→digest→send)
  app.py               wiring: long-poll listener + scheduler
  __main__.py          CLI (run | digest | parse)
tests/                 50 tests, fully offline
development/           Arcanum artifacts (SPEC, GLOSSARY, ARCHITECTURE, plan)
```

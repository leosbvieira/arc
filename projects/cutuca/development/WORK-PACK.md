---
artifact: work-pack
capability: cutuca
authored_by: invoke/plan
status: baseline
complexity: medium
output_mode: single-file
source_refs: [SPEC.md, ARCHITECTURE.md, IMPLEMENTATION-LAYERING.md]
---

# WORK-PACK — cutuca

**Objective:** Build v0 of cutuca — Flow A (capture) and Flow B (nudge) — as a
long-poll Python service with isolated model/channel seams, plus the Arcanum
governance artifacts. Live-credential validation is owner-run; everything else is
proven by unit tests with mocked network.

**Dispatch technique trace:** `sequence` (design → tasks), `scu_swu_reduction`
(each task is one smallest coherent unit), `recomposition_proof` (tasks recompose
into ARCHITECTURE views), `validation_loop` (every task has a check),
`owner_boundary_check` (invoke authored; task-session/owner execute), `residue_ledger`
(deferred items tracked in layering), `execution_receipt_handoff` (live-cred steps
name owner as executor).

## Task board (layer-mapped waves)

| ID | Layer | Task | Validation | Owner |
|---|---|---|---|---|
| T-01 | L0 | Project scaffold: pkg, config, logging, deps, `.env.example`, `.gitignore` | package imports; config loads example | done |
| T-02 | L0 | `cadence.py` pure rules (TDD) | `test_cadence.py` green | done |
| T-03 | L0 | `state.py` SQLite dedupe (TDD) | `test_state.py` green | done |
| T-04 | L0 | `parser.py` `parse_task` with injectable client + strict JSON | `test_parser.py` green (fake client) | done |
| T-05 | L0 | `clickup.py` REST v2 client (create/list, timeouts) | `test_clickup.py` green (mocked requests) | done |
| T-06 | L1 | `capture.py` pipeline + ask-back | `test_capture.py` green | done |
| T-07 | L1 | `telegram_channel.py` send seam + long-poll wiring | import-safe; send seam unit-tested | done |
| T-08 | L2 | `nudge.py` digest: select → dedupe → format → send | `test_nudge.py` green | done |
| T-09 | L2 | `app.py`/`__main__` wire long-poll + APScheduler | import-safe; boot smoke | done |
| T-10 | L2 | Structured logging + network/timeout handling threaded through | covered in module tests | done |
| T-11 | L3 | README runbook: setup, secrets, run, deploy, serverless note | manual review | done |

## Smallest Working Units (selected, medium-complexity core logic)

- **SWU-CUT-001** (T-02): `needs_nudge(task, rule, today)` — due-today OR overdue OR
  stale-by-N. Write scope: `cadence.py`. Accept: table tests for each predicate + combo.
- **SWU-CUT-002** (T-02): `tone(days_overdue)` bucketed escalation. Accept: bucket tests.
- **SWU-CUT-003** (T-03): dedupe `(task_id, day)` idempotency. Accept: double-mark = one row; `already_nudged` truthy after mark.
- **SWU-CUT-004** (T-04): strict-JSON parse with ask-back on failure/missing field.
  Accept: valid→dict; malformed→None; missing assignee/prazo→None.
- **SWU-CUT-005** (T-08): digest excludes already-nudged-today, escalates tone, marks after send.
  Accept: two runs same day → one nudge per task.

## Validation strategy

- Pure logic (cadence, state, parser, capture, nudge) validated by `pytest`, no network.
- Network clients validated with mocked `requests` / injected fake model client.
- Live validation (real Telegram/ClickUp/Anthropic) is an **owner-run** acceptance
  step documented in README; requires the four secrets.

## Distill validation

- Smallest coherent unit: each task edits one module. **pass**
- Recomposition: tasks reassemble into the six ARCHITECTURE views. **pass**
- Hidden gaps: live-credential acceptance is owner-owned (not blockable here) — recorded.
- Overbuild check: no serverless, no channel abstraction beyond one seam, no ORM. **pass**
- Verdict: **pass** (with named live-cred residue).

## Blocker / gap ledger

- **G-1 (owner):** four secrets + `clickup_list_id` required before live acceptance. Non-blocking for build.
- **G-2 (owner):** ClickUp assignee resolution (name → user id) needs the real workspace member list; v0 ships a resolver that fetches members and matches by name, tuned live.

**Next route:** `task-session` executed inline this session for T-01…T-11;
live acceptance handed to owner.

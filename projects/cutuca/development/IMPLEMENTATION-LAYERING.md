---
artifact: implementation-layering
capability: cutuca
authored_by: invoke/plan
status: baseline
source_refs: [SPEC.md, ARCHITECTURE.md]
---

# IMPLEMENTATION-LAYERING — cutuca

Maps the brief's Fase 0–3 onto Arcanum L0–L3 layer boundaries. Promotion between
layers requires evidence from the previous layer, not preference.

| Layer | Question it answers | Slice | Promotion evidence |
|---|---|---|---|
| **L0** (Fase 0) | Do the three integrations even work in isolation? | Echo bot; isolated `parse_task` with strict JSON; hardcoded ClickUp create. | Echo round-trips; `parse_task` returns valid dict on a fixture; one real task appears in ClickUp. |
| **L1** (Fase 1) | Does the full capture pipeline work, and does it refuse garbage? | Wire message → parse → create → confirm; ask-back on incomplete/ambiguous. | Normal message → correct task + confirm; ambiguous message → ask-back, no task. |
| **L2** (Fase 2 + 3) | Can it chase reliably without spam, and survive failures? | Flow B: read → cadence select → dedupe → digest → scheduler; structured logging; network/timeout handling. | Digest run twice/day chases each task once with escalating tone; parse/network failure degrades safely. |
| **L3** (deploy) | Is it runnable unattended? | Long-poll host runbook (systemd/pm2/Task Scheduler) + config finalization. Serverless path documented, not built. | Process stays up; digest fires on schedule on the host. |

**Layer window for this build session:** L0 → L2 authored as code + tests now
(network-bound behavior validated via mocks; live-credential validation is owner-run).
L3 is a runbook, not code.

**Deferred complexity (residue):** voice capture, WhatsApp channel, Outlook ingestion,
serverless deployment. All isolated behind existing seams; none block v0.

---
artifact: glossary
capability: cutuca
authored_by: invoke/define
status: baseline
---

# GLOSSARY — cutuca

| Term | Definition | Linking |
|---|---|---|
| **Capture (Flow A)** | Event-driven path: a Telegram message becomes a ClickUp task at send time. | linked → SPEC §3 |
| **Nudge / Cutucada (Flow B)** | Scheduled path: a digest that reminds the owner which tasks to chase. | linked → SPEC §3 |
| **Digest** | One formatted message summarizing tasks that need chasing today. Delivered to the owner only. | linked → SPEC FR-4 |
| **Cadence rule (`cobrar_se`)** | The predicate deciding whether a task needs chasing today: `vence_em_dias` (due within N days), `atrasada` (any overdue), `sem_update_dias` (untouched for N days). | linked → SPEC FR-4 |
| **Dedupe** | Persistence of "task X was already nudged on day Y" so the same task is not repeated identically the same day. | linked → SPEC FR-5 |
| **Tone escalation (`escala_tom`)** | Digest wording gets firmer as a task's days-overdue grows. | linked → SPEC FR-5 |
| **parse_task** | The single isolated function turning free text into `{assignee, titulo, prazo_iso, lista}` via Haiku, returning strict JSON. | linked → SPEC FR-3 |
| **Ask-back** | Bot reply requesting a missing field (assignee/prazo) instead of creating an incomplete task. | linked → SPEC FR-2 |
| **Channel / Canal** | The delivery medium (Telegram in v0). Isolated behind one send function so it is swappable. | linked → SPEC NFR-4 |
| **Owner** | The single human (Leo) who sends tasks and receives every nudge. | linked → SPEC §2 |
| **Assignee** | The employee a ClickUp task is assigned to. Referenced only; not a bot user in v0. | linked → SPEC §2 |
| **Target list (`clickup_list_id`)** | The ClickUp list holding employee tasks that Flow B reads and Flow A writes to. | linked → SPEC §7 |
| **Long-poll** | v0 listener: a running Python process that polls Telegram for updates. | linked → SPEC §4 |
| **Serverless path** | Fase-2 alternative: Telegram webhook → API Gateway → Lambda, DynamoDB state, EventBridge cron. | no-match (future) |

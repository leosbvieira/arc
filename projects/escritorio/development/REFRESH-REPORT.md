---
artifact: refresh-report
capability: escritorio
authored_by: invoke/refresh
mutation_mode: apply-approved
phase_status: pass
source: "design conversation pasted 2026-06-30 (task-bot → personal agent hub → Hermes)"
status: baseline
---

# REFRESH-REPORT — cutuca → escritório

Arcanum `invoke refresh`: maps the design conversation (new session evidence) into artifact
deltas. Mutation mode `apply-approved` — user said "escreve". Every change ties to a signal.

## Source signals
| id | type | claim | → target |
|---|---|---|---|
| S-1 | route_changed | Scope grew: employee task-bot → personal AI agent hub (5 needs + task-manager-by-area). | new `escritorio` project |
| S-2 | status_changed | Platform is open (not LibreChat); anchor on use cases. | DISCOVERY, DECISIONS |
| S-3 | evidence_added | Obsidian → GitHub repo (gives it an API; kills local-sync). | D-3 |
| S-4 | status_changed | ClickUp = single task home, one Space per life-area (Trabalho/Finanças/Saúde/Pessoal); TickTick retired. | D-2 |
| S-5 | route_changed | Surface = Escritório (cockpit) chosen; then unified with reach. | D-6 |
| S-6 | evidence_added | Hermes Agent verified: API-key auth, MCP, built-in cron, API server (REST + OpenAI-compatible + WS), profiles, $5-VPS/no-GPU. | D-4, ARCHITECTURE |
| S-7 | blocker_resolved | Cockpit feasible on Hermes: dashboard + Open WebUI/LobeChat + custom via API server. | D-6, ARCHITECTURE |
| S-8 | status_changed | cutuca runtime superseded by Hermes cron + ClickUp MCP; rules → skill spec. | D-10 |

## Applied changes
- **Created** `escritorio/` with README, DISCOVERY, DECISIONS, ARCHITECTURE, RUNBOOK, this report.
- **Repositioned** `cutuca` from primary deliverable to cadence spec + fallback runtime (D-10).

## Skipped / preserved (no silent promotion)
- cutuca code + tests untouched (still valid; the fallback path if Hermes is rejected).
- Email/Outlook, WhatsApp, voice, custom cockpit, local models — left as explicit deferrals (DECISIONS).

## Blockers / open (owner)
- U-1..U-5 in DISCOVERY (email scope, TickTick migration, recency model, cockpit path, Hermes maturity) — all non-blocking, sequenced in RUNBOOK.
- Owner still owes tokens/keys before live: ClickUp token, GitHub PAT, model API key (+spend cap), Telegram bot token.

## Validation
- Design self-consistency: 5 needs each map to a component in ARCHITECTURE View 3. ✅
- Glass-not-store invariant holds across all workflows (View 4/5). ✅
- ToS constraint encoded as a decision gate (View 5, D-5). ✅
- Live validation is owner-run per RUNBOOK "prove it" checks.

## Next route
`task-session` per RUNBOOK stage (owner-executed on the mini-server), prove-before-invest at stages 1–3.

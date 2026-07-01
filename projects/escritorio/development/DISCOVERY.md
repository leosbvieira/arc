---
artifact: discovery-baseline
capability: escritorio
authored_by: scope-interview
mode: greenfield (mixed — supersedes cutuca)
status: baseline
---

# DISCOVERY — escritório

Separates what is **observed** (evidence), **stated** (user said), **decided** (locked
with rationale), and **unresolved** (still open). Discovery is platform-neutral by
intent; the platform (Hermes) was chosen only after the needs were fixed.

## Actor
- **Leo** — single user/owner. Founder, mid-ConsigVerse. Self-describes as forgetful,
  voice-first (Wispr), prone to "build the perfect system" as productive procrastination.
  Not a product; no other users in scope.

## Stated needs (the 5, verbatim intent)
1. Talk to a personal AI chat, possibly several agents (X, Y), each connectable to Claude/GPT.
2. Agents retrieve his material (Obsidian notes, ClickUp tasks, emails).
3. Agents write into his stores (Obsidian, ClickUp).
4. Reminders that nudge him (he first said "every X hours"; corrected to digest + escalation).
5. Each agent follows a workflow; heavy work runs on the real Claude binary (OAuth) as batch.
   Plus (added mid-interview): a **task-manager view by life-area with recency** —
   "olhar a área Saúde, ver todas as tasks e a última vez que fiz".

## Decided (see DECISIONS.md for rationale)
- **Sources of truth stay external** — glass-not-store invariant.
- **ClickUp = single home for ALL tasks**, one Space per **life-area: Trabalho, Finanças,
  Saúde, Pessoal**. TickTick retired for tasks.
- **Obsidian vault → GitHub repo** (gives it a real remote/API; kills the local-sync problem).
- **Surface = both**: Telegram (reach) + a web cockpit (consult) — unified by one engine.
- **Engine = Hermes Agent** (self-hosted, API-key auth, MCP, cron, messaging, profiles).
- **Cockpit** = Hermes dashboard / Open WebUI / LobeChat now; custom app later.
- **Auth for models = API keys** (or a router / Nous Portal). Subscription OAuth only in the
  real `claude` binary for batch. Not negotiable — ToS wall from Feb-2026.
- **Reminder cadence = digest + tone escalation, config-driven, not interval spam.**
- **Host = a small always-on mini-server** (or PC-on). Runs Hermes + cron + MCP.
- **cutuca** repositioned: runtime superseded, cadence rules promoted to Hermes skill spec.
- **Hermes over LibreChat**: LibreChat is a pure web console; Hermes is engine+reach+memory+cron
  and *also* fronts any cockpit via its API server, so it covers more with one piece.

## Observed (evidence)
- `../cutuca` exists and works: Haiku parser, ClickUp REST client, cadence+dedupe digest,
  Telegram send; **50 tests passing**. Maps to needs #2/#3 (ClickUp) + #4 (reminder).
- A **ClickUp MCP** is already connected in the working session (`mcp__clickup__*`) — ClickUp
  connectivity may be off-the-shelf, not custom.
- Hermes Agent (verified in repo/docs): API-key auth (or Nous Portal); native **MCP**; **built-in
  cron scheduler**; **API server** with REST (`/api/sessions/*`, `/v1/*`) + OpenAI-compatible
  endpoint + WebSocket; **profiles** (persona/model/tool config, selectable); Telegram/Discord/
  Slack/WhatsApp/Signal/CLI gateway; runs on a $5 VPS, no GPU; `curl` install.

## Unresolved (open, non-blocking)
- **U-1 Email/Outlook** — deferred to phase 2 (MS Graph OAuth is the chatty part). Which
  email use case matters first (read for context? draft replies?) TBD.
- **U-2 TickTick migration** — how much personal/health history to migrate vs start fresh in
  ClickUp. Can be gradual.
- **U-3 "última vez que fiz" model** — recurring-task completion vs a `feito em` custom field.
  Pick per task type when setting up ClickUp Spaces.
- **U-4 Cockpit path** — adopt Hermes dashboard vs Open WebUI vs LobeChat first. Decide by
  trying the built-in dashboard (cheapest) in RUNBOOK stage 7.
- **U-5 Hermes maturity** — ~4 months old, open bugs on dashboard WebSocket auth. Fallback if it
  fights back: LibreChat + cutuca cron (pieces still compose).

## Counter-position (kept honest)
- *"Just adopt LibreChat (mature) instead of a 4-month-old framework."* — Valid on maturity, but
  LibreChat is only the console; you'd still bolt on cron (cutuca) + batch + memory separately.
  Hermes' risk is age; its payoff is one engine covering reach+memory+cron+cockpit-API. Mitigated
  by prove-before-invest (RUNBOOK stages 1–3 are cheap and reversible).
- *"One agent, not many, is a downgrade."* — Hermes **profiles** recover the multi-agent feel; and
  one assistant that knows your whole life is arguably more coherent than juggling N.

## Verdict
**Ready for planning / build** — see RUNBOOK.md. No blocker decisions open; U-1…U-5 are
sequenced, non-blocking follow-ups.

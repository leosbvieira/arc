# escritório

Working name for Leo's **personal AI command center**: one self-hosted engine that
reaches him on Telegram, remembers him, runs unattended jobs, and is fronted by a
web cockpit — all sitting *over* his existing tools, never replacing them.

> **Engine = [Hermes Agent](https://github.com/nousresearch/hermes-agent)** (self-hosted,
> API-key auth, MCP tools, built-in cron, messaging gateway, learning/skills).
> **Cockpit = glass on top** (Hermes' built-in dashboard → Open WebUI/LobeChat → your own app).
> **Sources = ClickUp + a GitHub-hosted Obsidian vault.** The engine reads/writes them;
> it stores nothing canonical.

## The one invariant — glass, not store

The escritório never becomes "the place where a task lives." Everything it captures
round-trips to **ClickUp** (all tasks, by life-area) or the **Obsidian vault on GitHub**
(notes). The moment it holds canonical data it becomes the sixth scattered system that
dies — the exact trap this whole design exists to avoid.

## What it does (the 5 needs)

1. **Talk to it** — one assistant with selectable *profiles* (Tarefas, Notas…) via
   Telegram now, web cockpit next. (Hermes profiles ≈ your "multiple agents".)
2. **Retrieve** — "me mostra a área Saúde: o que tem e há quanto tempo não faço" →
   reads ClickUp / vault via MCP.
3. **Write** — "cobra a Ana sexta" / "anota: cap 3 do Sapiens fraco" → creates in
   ClickUp / appends to the vault.
4. **Remind** — morning digest of what to chase (Hermes cron), no interval spam,
   tone escalates with lateness. (This is the `cutuca` cadence logic, now a Hermes skill.)
5. **Heavy batch** — end-of-day review (Hermes cron): re-read tasks + vault, consolidate,
   propose.

## Layers

```
COCKPIT (glass)   dashboard embutido → Open WebUI/LobeChat → seu app próprio
      │  REST / OpenAI-compatible /v1  (API_SERVER_KEY)
HERMES (engine)   mini-server · API keys · memória/skills · cron · Telegram
      │  MCP
SOURCES (store)   ClickUp (Trabalho/Finanças/Saúde/Pessoal)  +  GitHub vault (Obsidian)
```

## Read next

- [development/DECISIONS.md](./development/DECISIONS.md) — every locked decision + why (D-1…D-11).
- [development/ARCHITECTURE.md](./development/ARCHITECTURE.md) — the engine design in views.
- [development/DISCOVERY.md](./development/DISCOVERY.md) — scope baseline (observed/decided/open).
- **[RUNBOOK.md](./RUNBOOK.md) — build order for the mini-server (the Hermes engine).** ← engine first.
- [development/APP-ARCHITECTURE.md](./development/APP-ARCHITECTURE.md) — the custom cockpit app (glass over Hermes).
- [development/APP-WORK-PACK.md](./development/APP-WORK-PACK.md) — the app's layered build plan (L0→L3).
- [development/CAPTURE-GRAMMAR-SPEC.md](./development/CAPTURE-GRAMMAR-SPEC.md) — the 6-mode reading capture grammar (lane #1).
- [development/REMINDER-SKILL-SPEC.md](./development/REMINDER-SKILL-SPEC.md) — the digest/nudge skill (ported from cutuca).
- [development/REFRESH-REPORT.md](./development/REFRESH-REPORT.md) — how this supersedes the earlier `cutuca` design.

## Relationship to `cutuca`

`../cutuca` is the working Telegram→ClickUp capture+nudge bot built first. In this
architecture its **runtime is superseded** by Hermes' cron + ClickUp MCP, but its
**cadence rules** (what counts as due/overdue/stale, dedupe, tone escalation) are the
validated spec for the Hermes reminder skill. Not wasted — promoted to spec.

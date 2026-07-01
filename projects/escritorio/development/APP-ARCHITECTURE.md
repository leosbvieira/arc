---
artifact: architecture-bundle
capability: escritorio-app
profile: domainspec-architecture
status: baseline
source_refs: [ARCHITECTURE.md, DECISIONS.md, CAPTURE-GRAMMAR-SPEC.md]
implements: D-11 (custom app = primary capture+consult surface, glass over Hermes)
---

# APP-ARCHITECTURE — o app próprio (cockpit do escritório)

O app é a **superfície principal** de captura + consulta (D-11), e é **vidro sobre o Hermes**:
ele não roda LLM, não fala com ClickUp/GitHub direto, não guarda nada canônico. Ele manda
texto pro Hermes e mostra o que volta.

## Stack (decidido)
- **Django + HTMX + Tailwind** — app Python server-rendered (UI + backend juntos).
  Motivo: Python (teu músculo); **auth/sessão/admin de graça** (o app precisa de login
  single-user — Django entrega pronto, e o admin serve de janela de debug); maduro/estável;
  Django+HTMX é ergonômico; o segredo (chave do Hermes) fica no servidor por natureza;
  instalável como **PWA**. Voz = Wispr digita em qualquer campo.
- **Glass-not-store preservado:** SEM models de domínio — só as tabelas de auth/sessão do
  próprio Django num SQLite. Task e nota moram no ClickUp/vault, nunca no app.
- **Alternativas:** FastAPI+HTMX (proxy mais leve, sem baterias) ou React SPA (UX mais rica
  depois). Em qualquer caso troca só o app; Hermes/vault/contrato ficam iguais.

## Componentes / deployment
```
┌─ celular/PC (browser, PWA instalável) ─────────────┐
│  UI (HTMX + Tailwind, server-rendered)             │
└───────────────┬────────────────────────────────────┘
                │ HTTPS (login single-user)
┌───────────────▼──────────── VPS ($5–10/mês) ───────┐
│  APP (Django)  = UI + BFF                           │
│   • auth de 1 usuário (django.contrib.auth)         │
│   • guarda HERMES_API_KEY (nunca vai pro browser)   │
│   • proxy p/ Hermes: /api/sessions, /v1             │
│                     │                                │
│  HERMES (motor)  ◀──┘  profiles: Leitura/Tarefas/Notas
│   • LLM (API key/router) · memória/skills · cron    │
│   • MCP                                              │
└───────────┬───────────────────────┬─────────────────┘
       ClickUp MCP              GitHub MCP
     (tasks por área)        (vault Obsidian)
```
App e Hermes co-moram no VPS (o app chama o Hermes em localhost). Segredos das fontes
(ClickUp token, GitHub PAT, model key) moram no Hermes; a chave do Hermes mora no app. **Nada
disso toca o browser.**

## Views (v1 → v2)
| View | O que faz | Como |
|---|---|---|
| **Capturar** (home) | Caixa de texto (Wispr digita) + seletor de profile (Leitura/Tarefas/Notas) → envia. Pra leitura: mostra os itens da sessão + botão "compilar". | POST texto → Hermes(profile) → grava no destino (vault/ClickUp) |
| **Tarefas** | Task manager por área (Trabalho/Finanças/Saúde/Pessoal) com recência ("última vez há X"). Criar/concluir. | Hermes → ClickUp MCP (lê por Space) |
| **Chat** | Conversa livre com um profile. | Hermes /v1 (OpenAI-compatible) |
| **Revisão** (v2) | Digest do dia + itens ★ pra Anki. | Hermes cron/consulta |

## Fluxo por view (exemplo: Capturar-Leitura)
1. Wispr digita "livro: Antifrágil, p.85 … comentário: …" na caixa.
2. App POST `/capture` → BFF chama Hermes profile **Leitura** com o texto.
3. Hermes aplica a CAPTURE-GRAMMAR (6 modos) → GitHub MCP anexa na nota do dia no vault.
4. App mostra "✅ anotado"; "compilar" finaliza a sessão.
Repare: o app só transporta texto e mostra resultado. A gramática/escrita é do Hermes.

## Segurança
- **Single-user:** `django.contrib.auth` (login → sessão). Sem cadastro público.
- **Segredos server-side:** `HERMES_API_KEY` no `.env` do app; tokens de fonte no Hermes. Nunca no HTML/JS.
- **HTTPS:** Caddy/nginx no VPS (cert automático). Acesso privado (Tailscale ou domínio + auth).
- **Sem store canônico:** o app pode ter SQLite só pra estado de UI/sessão — nunca task/nota.

## O que o app NÃO faz (trilhos)
- Não chama LLM direto (é o Hermes). Não fala com ClickUp/GitHub direto (é o MCP do Hermes).
- Não vira fonte da verdade (D-1). Se começar a guardar task/nota, virou o sexto silo.

## Dependências
- **Hermes de pé** (RUNBOOK estágios 0–6) — o app é vidro sobre ele; sem motor, não há o que vestir.
- **Ponte enquanto o app não existe:** capturar leitura por Telegram (Hermes) ou Claude Code coding
  session no vault. Migrar pro app depois = trocar o vidro, zero retrabalho.

## Riscos
- Hermes ~4 meses (bugs no dashboard/WebSocket) → o app usa a REST/`/v1` do Hermes, que é mais
  estável que o dashboard; se travar, fallback Telegram.
- Escopo: é um app de verdade (dias de trabalho, não uma tarde). Fino-sobre-Hermes mantém limitado.

---
artifact: architecture-bundle
capability: escritorio-app
profile: domainspec-architecture
status: baseline
source_refs: [ARCHITECTURE.md, DECISIONS.md, CAPTURE-GRAMMAR-SPEC.md, REMINDER-SKILL-SPEC.md]
implements: D-11 (app = superfície primária), D-12 (stack Expo/RN nativo), D-13 (BFF fino), D-14 (push FCM + Telegram)
supersedes: baseline anterior deste arquivo (Django + HTMX + PWA)
---

# APP-ARCHITECTURE — o app do escritório (cockpit nativo)

O app é a **superfície principal** de captura + consulta (D-11) e é **vidro sobre o Hermes**:
não roda LLM, não fala com ClickUp/GitHub direto, não guarda nada canônico. Agora ele é um
**app Android nativo (Expo/React Native)** que conversa com um **BFF fino (FastAPI)** no VPS —
e é *o BFF*, não o app, que fala com o Hermes.

## Stack (decidido — supersede o baseline Django+HTMX+PWA)
- **App: Expo (React Native), Android primeiro** (D-12). App "de verdade" na home, com **push FCM
  confiável dentro do app**. O mesmo código serve iPhone depois.
- **BFF: FastAPI (Python) no VPS** (D-13). Guarda `HERMES_API_KEY`, faz auth single-user, proxy
  pro Hermes, e é o **relay de push** (recebe o digest do cron do Hermes → dispara FCM). Leve —
  só JSON, sem templates/admin.
- **Por que existe um BFF:** um cliente nativo **não pode embutir a chave do Hermes** (extraível
  do APK). O segredo tem que morar num servidor; o BFF é esse servidor mínimo.
- **Glass-not-store preservado:** nem o app nem o BFF guardam task/nota. O BFF tem um SQLite só
  pra: sessão de auth (1 usuário) + tokens de device FCM. Task e nota moram no ClickUp/vault, via
  Hermes.
- **Alternativa:** BFF em Node/Express (mesma linguagem do app). FastAPI escolhido por ser teu
  forte (Python) e o `cutuca` já ser Python (dá pra reusar a cadência se um dia o BFF precisar).

## Componentes / deployment
```
┌─ celular Android — app Expo (React Native) ─────────┐
│  telas: Capturar · Tarefas · Chat · Revisão         │
│  recebe push FCM (nudge/digest)                     │
└──────────────┬──────────────────────────▲───────────┘
               │ HTTPS (token de sessão)   │ push FCM
               │                           │
┌──────────────▼──────────── VPS ($5–10/mês) ──────────┐
│  BFF (FastAPI)                                        │
│   • auth 1 usuário → emite token de sessão            │
│   • guarda HERMES_API_KEY (nunca vai pro celular)     │
│   • proxy p/ Hermes:  /api/sessions,  /v1             │
│   • POST /devices          registra token FCM         │
│   • POST /internal/notify  recebe digest → dispara FCM│
│                     │ localhost                        │
│  HERMES (motor)  ◀──┘  profiles: Leitura/Tarefas/Notas │
│   • LLM (API key/router) · memória/skills · cron       │
│   • cron reminder-digest → Telegram + POST /internal/notify
│   • MCP                                                │
└──────────┬────────────────────────┬──────────────────┘
      ClickUp MCP               GitHub MCP
    (tasks por área)         (vault Obsidian)
```
App, BFF e Hermes: o app fala HTTPS com o BFF; o BFF chama o Hermes em localhost. **Segredos das
fontes** (ClickUp token, GitHub PAT, model key) moram no Hermes; **`HERMES_API_KEY`** mora no BFF;
a credencial de push é **gerenciada pela Expo/EAS** (não fica no BFF). O celular só guarda o **token
de sessão** dele e o **Expo push token** do device. Nada sensível dentro do APK.

## Push — como a notificação chega no app (D-14)
1. App abre → pede permissão → pega o **Expo push token** → manda pro BFF (`POST /devices`).
2. Cron do Hermes roda a skill **`reminder-digest`** (ver REMINDER-SKILL-SPEC): calcula o digest
   (due/overdue/stale, dedupe, tom) — regra determinística, o LLM só formata.
3. Hermes entrega no **Telegram** (backbone confiável) **e** faz `POST /internal/notify` no BFF
   com o texto do digest.
4. BFF faz **fan-out via Expo Push Service** (que gerencia o FCM por baixo) pros tokens
   registrados → notificação aparece no app; tocar abre a tela **Tarefas**.

Uma fonte só do digest (o Hermes). O BFF é só relay. Se o app/FCM falhar (OEM mata background,
etc.), o **Telegram garante o aviso** — por isso ele é o backbone e o push do app é reforço.

## Telas (v1 → v2)
| Tela | O que faz | Como |
|---|---|---|
| **Capturar** (home) | Caixa de texto (Wispr digita) + seletor de profile (Leitura/Tarefas/Notas) → envia. Pra leitura: mostra os itens da sessão + botão "compilar". | POST texto → BFF → Hermes(profile) → grava no destino (vault/ClickUp) |
| **Tarefas** | Task manager por área (Trabalho/Finanças/Saúde/Pessoal) com recência ("última vez há X"). Criar/concluir. | BFF → Hermes → ClickUp MCP (lê por Space) |
| **Chat** | Conversa livre com um profile. | BFF → Hermes `/v1` (OpenAI-compatible) |
| **Revisão** (v2) | Digest do dia + itens ★ pra Anki. | Hermes cron/consulta via BFF |

## Fluxo por tela (exemplo: Capturar-Leitura)
1. Wispr digita "livro: Antifrágil, p.85 … comentário: …" na caixa do app.
2. App `POST /capture` → BFF chama o Hermes profile **Leitura** com o texto.
3. Hermes aplica a CAPTURE-GRAMMAR (6 modos) → GitHub MCP anexa na nota do dia no vault.
4. App mostra "✅ anotado"; "compilar" finaliza a sessão.
O app só transporta texto e mostra resultado; o BFF só faz proxy+auth; a gramática/escrita é do Hermes.

## Auth / segurança
- **Single-user:** login no app (senha no `.env` do BFF, ou pareamento por código) → o BFF emite um
  **token de sessão** → o app guarda no **SecureStore** do device. Sem cadastro público.
- **Segredos server-side:** `HERMES_API_KEY` no BFF; tokens de fonte no Hermes; a credencial de
  push fica no **EAS** (gerenciada pela Expo). Nunca no app/APK.
- **HTTPS:** Caddy/nginx no VPS (cert automático). Acesso privado (domínio + auth; Tailscale opcional).
- **Sem store canônico:** o BFF pode ter SQLite só pra auth/sessão + device tokens — nunca task/nota.

## O que o app / BFF NÃO fazem (trilhos)
- O **app** não chama LLM nem ClickUp/GitHub direto. O **BFF** não chama LLM nem MCP — quem faz é o
  Hermes. O BFF só: auth, proxy pro Hermes, e relay de push.
- Nada vira fonte da verdade (D-1). Se o app/BFF começar a guardar task/nota, virou o sexto silo.

## Dependências
- **Hermes de pé** (RUNBOOK estágios 1–5) — o app é vidro sobre ele.
- **Destrava começar já:** L0 e boa parte do L1 dão pra construir **em paralelo** contra um Hermes
  **mockado** (local, sem VPS); plugar o Hermes real é trocar a URL base. O engine sobe em paralelo.
- **Ponte enquanto o app não existe:** captura + nudge por **Telegram** (cutuca/Hermes) já funciona.
  Migrar pro app depois = trocar o vidro, zero retrabalho.

## Riscos
- Hermes ~4 meses (bugs no dashboard/WebSocket) → o BFF usa a REST/`/v1` do Hermes, mais estável
  que o dashboard; se travar, fallback Telegram.
- FCM/OEM: alguns Androids matam background agressivo → por isso o Telegram é o backbone e o push do
  app é reforço.
- Escopo: app nativo **+** BFF é trabalho de dias, não de uma tarde. Fino-sobre-Hermes segura o escopo.

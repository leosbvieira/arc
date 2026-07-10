# Sessão de sábado — Task 7 + ativação + aceitação (P1)

> Tempo estimado: 40-60 min com o Leo na tela. Ordem importa: **segredos → vault/PATs → Telegram → cron → drills**.
> Código está pronto (25 commits, 106 testes verdes, review duplo Claude+GPT aprovado). Esta sessão liga e prova.

## 0. ⚠ PRIMEIRO: segredos (o BFF RECUSA BOOT sem isso — guard fail-closed novo)

No `projects/escritorio/bff/.env`:
- [ ] `APP_PASSWORD` → senha forte nova (a atual tem 10 chars)
- [ ] `JWT_SECRET` → ≥32 bytes aleatórios (a atual tem 25; gerar: `python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- [ ] `INTERNAL_TOKEN` → valor novo (o atual está NO DEFAULT do código → boot bloqueado)
- Efeito colateral: app pede login de novo (token de sessão invalida). Normal.

## 1. Vault — reconciliação (com o Claude conduzindo, conflitos são teus)

Em `C:\Users\Leonardo\Documents\LeonardoLifeMain`:
- [ ] Fotografar: `git status` / `git log --oneline -8` / `git log --oneline origin/main -5`
- [ ] `git add -A && git commit -m "wip: estado local pre-reconciliacao"`
- [ ] `git merge origin/main` → resolver conflito a conflito (HOME.md, Weekly/2026-W27.md, plugins)
- [ ] `git push origin main` → `git status` limpo
- [ ] Obsidian: conferir pull automático do obsidian-git

## 2. PATs GitHub (5 min, no teu navegador)

- [ ] Criar **PAT-1 (BFF)**: fine-grained, só repo `leosbvieira/aeternum`, permission Contents: Read/Write → colar em `bff/.env` como `GITHUB_PAT=`
- [ ] Criar **PAT-2 (Hermes)**: mesmo escopo → substituir em `C:\Users\Leonardo\AppData\Local\hermes\config.yaml` (linha ~203)
- [ ] **REVOGAR o PAT antigo exposto** (github.com/settings/tokens — o que está hoje na config do Hermes)
- [ ] Testar Hermes segue ok: 1 captura pela DM do Telegram

## 3. Contrato do vault (Q9 + spec §8) — 2 edições no CLAUDE.md do vault

- [ ] terapia: de 10º modo → flag `mode=reflexao, sensitive=true, sensitive_reason=terapia`; contador = 10 modos (captura…empresa)
- [ ] documentar tag `field/edificacao` + naming do Raw do escritor BFF: `YYYY-MM-DD - raw-c{id}.md` (neutro)
- [ ] commit+push (Claude redige, tu aprovas)

## 4. Telegram (gate Q3)

- [ ] Copiar o bot token do Hermes (`AppData\Local\hermes\.env` ou config) → `bff/.env`: `TELEGRAM_BOT_TOKEN=`
- [ ] `TELEGRAM_CHAT_ID=8532026495`

## 5. Smoke do vault_client (gate da Task 8)

- [ ] `cd projects/escritorio/bff && PYTHONPATH=. ./.venv/Scripts/python.exe -c "import asyncio; from app import vault_client as v; print(asyncio.run(v.write_raw('teste vault_client bff - pode apagar', 'smoke')))"`
- [ ] Conferir commit `raw: csmoke` no origin (autor = PAT novo) e o arquivo aparecendo no Obsidian após pull

## 6. Cron (instalação real)

- [ ] `powershell -File projects\escritorio\bff\scripts\install-cron.ps1` (se o auto-mode do Claude barrar, tu roda com `!`)
- [ ] Conferir: 4 tasks listadas + `/health` respondendo
- [ ] Firewall: porta 8000 só no perfil Privado da rede

## 7. Drills de aceitação (T17 — runbook completo no plano; os principais)

| # | Drill | Prova |
|---|---|---|
| 1 | Captura normal pelo app | ✅ imediato; Raw `raw-cN` no origin ≤1 min |
| 2 | "comprar filtro amanhã" | Raw + task na **Staging** com `[cap:N] raw:` |
| 3 | "cobrar o Yan às 15h" | Staging + tag aguardando + due + ⏰ genérico na hora |
| 4 | `HERMES_BIN` inválido → capturar → restaurar | ✅; Raw ok; retry processa; `last_error` sem conteúdo |
| 5 | 5 falhas seguidas → `POST /captures/retry-failed` | item failed → volta pending (digest mostrava "⚠ N não processadas") |
| 6 | BFF desligado → 2 capturas → religar | badge "2 na fila"; flush em ordem |
| 7 | Task "Marcar psiquiatra" (Corpo, due ontem) + digest | Telegram: "1 pendência de saúde" SEM a palavra; app mostra completa |
| 8 | Digest só com staging velho | mensagem sai mesmo assim |
| 9 | PC suspenso às 9h → acordar | digest dispara no wake |
| 10 | Matar BFF → trigger digest | script religa e entrega |
| 11 | A3 pleno (editar 1 palavra) + retry | Daily com texto EXATO; sem bloco duplicado |
| 12 | A3 mínimo cronometrado | ≤ 90s |
| 13 | 2º fechamento no mesmo dia (despejo diferente) | 2º Raw TAMBÉM gravado (id com hash) |
| 14 | PAT inválido durante compilar de sessão → corrigir → retry | Raw das notas recuperado (dedup re-tenta) |
| 15 | Nudge de domingo (trigger manual) | scorecard % embutido |

## 8. Investigações registradas (durante os drills)

- [ ] **Hermes oneshot**: tem flag de stdin? Tem perfil tool-free? (risco registrado: classify roda com MCPs do Hermes disponíveis; prompt manda não usar — validar comportamento real e, se possível, travar por config)
- [ ] Preview do Telegram no lockscreen: conferir na prática a neutralização (drill 7)

## 9. Teu conteúdo (sem código)

- [ ] Plano de 10 anos → vault (hierarquia D19, `05 - Projetos`/estrutura da spec)

---
*Backlog P2 consolidado: ver `.superpowers/sdd/progress.md` (seção ONDA FINAL) e os reports em `.superpowers/sdd/`.*

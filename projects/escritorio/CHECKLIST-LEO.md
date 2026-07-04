# ✅ CHECKLIST DO LEO — o que só você pode fazer

O que precisa das suas mãos (celular, contas, VPS). O resto (código, instalação de deps, venv,
npm, IP no `BFF_URL`) **já foi feito**. Marque conforme avança.

---

## A) Rodar o L0 agora (captura, sem VPS) — 2 terminais

**Terminal 1 — BFF** (já instalado; roda em mock):
```powershell
cd C:\Users\LeonardoBalazs\Documents\GitHub\Arc\arc\projects\escritorio\bff
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — app** (já com deps + IP setado):
```powershell
cd C:\Users\LeonardoBalazs\Documents\GitHub\Arc\arc\projects\escritorio\app
npx expo start
```

- [ ] Instalei o **Expo Go** no Android (Play Store).
- [ ] Celular na **mesma Wi-Fi** da máquina.
- [ ] Escaneei o QR no Expo Go.
- [ ] Loguei com a senha `troque-esta-senha`.
- [ ] **Capturar:** digitei algo → vi `[mock:Leitura] anotado: …`. ✅
- [ ] **Tarefas:** abri a aba Tarefas → vejo tarefas por área (Saúde/Trabalho/…) com recência. ✅

> IP atual cravado no app: **192.168.80.109**. Se trocar de rede, rode `ipconfig`, pegue o IPv4
> da Wi-Fi e atualize `app/src/api.ts` → `BFF_URL`.

---

## B) Se o celular NÃO conectar no BFF
O Firewall do Windows costuma bloquear a porta 8000 pra entrada. Em um **PowerShell como
Administrador**:
```powershell
New-NetFirewallRule -DisplayName "escritorio BFF 8000" -Direction Inbound `
  -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```
- [ ] Liberei a porta 8000 (ou testei `http://192.168.80.109:8000/health` no navegador do celular).

---

## C) Push no app (quando quiser fechar a 2ª metade do L0)
Não roda no Expo Go — precisa de um dev build. Detalhe em `development/L0-SETUP.md` (passos 3–5).
```powershell
cd C:\Users\LeonardoBalazs\Documents\GitHub\Arc\arc\projects\escritorio\app
npm install -g eas-cli
eas login          # conta Expo grátis
eas init           # preenche o projectId no app.json
eas build --profile development --platform android
```
- [ ] Criei conta Expo + `eas login`.
- [ ] `eas init` (projectId preenchido).
- [ ] Gerei o dev build e instalei no celular.
- [ ] Rodei `npx expo start --dev-client`, loguei → app registrou o push token (`/devices` deu `count: 1`).
- [ ] Disparei o push de teste (passo 5 do L0-SETUP) e a notificação chegou. ✅
- [ ] Testei o **digest de cobranças** (calcula das tarefas com as regras do cutuca + faz push):
  ```powershell
  Invoke-RestMethod -Method Post http://localhost:8000/internal/run-digest -Headers @{ "X-Internal-Token" = "troque-token-interno" }
  ```

---

## D) Trilha ENGINE — subir o Hermes de verdade (RUNBOOK estágios 0–5)
Só você tem as contas/keys. Enquanto isso o app roda em mock. Ver `RUNBOOK.md`.

**Fontes (Stage 0):**
- [ ] ClickUp: criar 4 Spaces — **Trabalho, Finanças, Saúde, Pessoal** — e pegar o **token pessoal** + os IDs.
- [ ] Decidir o modelo de recência por área (tarefa recorrente vs campo `feito em`).
- [ ] Obsidian vault → repo **privado no GitHub** + **PAT fine-grained** (só esse repo, Contents R/W).
- [ ] Model key (Anthropic/OpenAI **ou** router) **com limite de gasto**.
- [ ] Telegram: `@BotFather` → `/newbot` → bot token.

**Engine (Stages 1–5):**
- [ ] VPS pequeno (US$5–10/mês), isolado do ConsigVerse.
- [ ] Instalar o Hermes (curl), conectar modelo + Telegram, MCP ClickUp + GitHub, profiles, skill de lembrete.

**Ligar o app no real:** no `.env` do BFF → `HERMES_MOCK=false` + `HERMES_BASE_URL` + `HERMES_API_KEY`.
(Confirmar o endpoint real em `bff/app/hermes_client.py` e a listagem de tarefas em `bff/app/tasks.py`.)

---

## E) Segurança (antes de qualquer uso real)
- [ ] `cd bff; copy .env.example .env` e troquei **APP_PASSWORD**, **JWT_SECRET** (string longa) e **INTERNAL_TOKEN**.
- [ ] Nunca comitar `.env` (já está no `.gitignore`).
- [ ] Limite de gasto na model key.

---

### Referências
- `development/L0-SETUP.md` — passo a passo detalhado do L0.
- `development/APP-WORK-PACK.md` — o mapa das camadas L0→L3.
- `RUNBOOK.md` — subir o engine (Hermes).
- `development/DECISIONS.md` — por que cada coisa é como é (D-1…D-14).

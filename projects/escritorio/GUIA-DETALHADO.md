# 🧭 GUIA DETALHADO — o que você (Leo) precisa fazer

Passo a passo com comandos exatos. Complementa o `CHECKLIST-LEO.md` (que é a versão marcável).

**Duas trilhas independentes:**
- **Trilha APP** (Fases 0–1): ver o app no celular + push. Rápido, quase sem contas.
- **Trilha ENGINE** (Fases 2–4): subir o Hermes real e ligar tudo. Mais longo.

**Ordem recomendada:** faça a **Fase 0 hoje** (10 min). Depois a Fase 1 (push) OU pule direto pra
trilha engine — elas não dependem uma da outra. A Fase 4 é o "flip" final que junta as duas.

> Onde estão os arquivos: `projects/escritorio/bff` (backend) e `projects/escritorio/app` (celular).
> Já rodei por você: venv+deps do BFF, npm install do app, e o IP `192.168.80.109` no `BFF_URL`.

---

## ✅ FASE 0 — Ver o app rodando agora (~10 min · tudo mock, zero conta)

**Pré:** instalar o app **Expo Go** no Android (Play Store). Celular na **mesma Wi-Fi** do PC.

### Passo 0.1 — Subir o BFF (Terminal 1)
```powershell
cd C:\Users\LeonardoBalazs\Documents\GitHub\Arc\arc\projects\escritorio\bff
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
✔️ **Pronto quando:** no navegador do PC, `http://localhost:8000/health` mostra `{"ok":true,"mock":true}`.

### Passo 0.2 — Confirmar que o celular alcança o BFF
No **navegador do celular**, abra: `http://192.168.80.109:8000/health`
- Mostrou o JSON → ótimo, pule pro 0.3.
- Não abriu → **Firewall**. Num PowerShell **como Administrador**:
  ```powershell
  New-NetFirewallRule -DisplayName "escritorio BFF 8000" -Direction Inbound `
    -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
  ```
  (Se o IP tiver mudado: `ipconfig` → IPv4 do adaptador Wi-Fi → atualize `app/src/api.ts` → `BFF_URL`.)

### Passo 0.3 — Rodar o app (Terminal 2)
```powershell
cd C:\Users\LeonardoBalazs\Documents\GitHub\Arc\arc\projects\escritorio\app
npx expo start
```
Abra o **Expo Go** no Android → **escaneie o QR** que apareceu no terminal.

### Passo 0.4 — Testar as 3 abas
Login com a senha `troque-esta-senha`, e verifique:
- **Capturar:** digite "cobrar Ana sexta" → aparece `[mock:Leitura] anotado: cobrar Ana sexta`.
- **Tarefas:** vê tarefas por área (Saúde, Trabalho…) com recência; consegue criar e concluir (✓).
- **Revisão:** vê "Cobranças de hoje (5)" com os marcadores 🚨/🟠/🟡.

✔️ **Fase 0 pronta.** O app está vivo (contra dados falsos). Nada disso é real ainda — é o esqueleto.

---

## 📲 FASE 1 — Push dentro do app (~45 min)

O push remoto **não funciona no Expo Go** — precisa de um "dev build". Esta é a parte mais chata
(por causa das credenciais do Android/FCM); o Telegram continua sendo o aviso confiável de qualquer forma.

### Passo 1.1 — Conta Expo + EAS
1. Crie conta grátis em **https://expo.dev**.
2. No terminal:
   ```powershell
   cd C:\Users\LeonardoBalazs\Documents\GitHub\Arc\arc\projects\escritorio\app
   npm install -g eas-cli
   eas login
   eas init      # cria o projeto e preenche o projectId em app.json
   ```
   ✔️ **Pronto quando:** `app.json` → `extra.eas.projectId` deixou de estar vazio.

### Passo 1.2 — Firebase/FCM (credencial de push do Android)
1. Em **https://console.firebase.google.com** → *Adicionar projeto* (nome à vontade; pode desligar Analytics).
2. Dentro do projeto: *Project settings* → aba **Service accounts** → **Generate new private key** →
   baixa um `.json`. **Guarde esse arquivo** (é o segredo do FCM; não comite).
3. Suba pro EAS:
   ```powershell
   eas credentials
   ```
   Escolha **Android** → **Push Notifications: Manage your FCM V1 credentials** → aponte o `.json`
   que você baixou. (Ou deixe o próprio `eas build` te guiar nisso no primeiro build.)

> Por que isso: no Expo Go a Expo usa o FCM dela; no *seu* build você fornece o seu FCM uma vez, e o
> EAS passa a gerenciar/injetar por você.

### Passo 1.3 — Gerar e instalar o dev build
```powershell
eas build --profile development --platform android
```
(usa o `eas.json` que já deixei pronto → gera um **APK** instalável). O build roda na nuvem da Expo
(grátis no free tier, ~10–20 min). Ao terminar, ele te dá um **QR/link** → baixe e **instale o APK** no celular.

### Passo 1.4 — Rodar no dev build e registrar o push
```powershell
npx expo start --dev-client
```
Abra o **app instalado** (não o Expo Go) → login → **conceda a permissão de notificação**.
✔️ **Pronto quando:** o app registrou o token — confirme no BFF: a resposta de `/devices` deu `count: 1`.

### Passo 1.5 — Disparar um push de teste
Com o BFF rodando (Fase 0), num terminal:
```powershell
Invoke-RestMethod -Method Post http://localhost:8000/internal/run-digest `
  -Headers @{ "X-Internal-Token" = "troque-token-interno" }
```
✔️ **Pronto quando:** a notificação **"🔔 5 cobranças de hoje"** aparece no Android. **Fase 1 fechada.**

---

## 🔌 FASE 2 — Fontes reais: ClickUp + vault + chaves (~1–2h)

### 2.1 ClickUp (casa das tarefas)
1. Crie **4 Spaces**: `Trabalho`, `Finanças`, `Saúde`, `Pessoal` (sidebar → **+**).
2. Decida como marcar recência ("última vez que fiz") por área:
   - hábitos/saúde → tarefa **recorrente** (a data de conclusão vira a "última vez");
   - one-offs → um campo custom `feito em`.
3. Pegue o **token pessoal**: ClickUp → *Settings* → *Apps* → **API Token** (começa com `pk_`).
4. Pegue os **IDs** (pra configurar o Hermes depois). No PowerShell:
   ```powershell
   $ck = @{ Authorization = "pk_SEU_TOKEN" }
   Invoke-RestMethod https://api.clickup.com/api/v2/team -Headers $ck          # pega team_id
   Invoke-RestMethod https://api.clickup.com/api/v2/team/TEAM_ID/space -Headers $ck   # space_ids por área
   Invoke-RestMethod https://api.clickup.com/api/v2/space/SPACE_ID/list -Headers $ck  # list_ids
   ```
   Anote os IDs das 4 áreas.

### 2.2 Vault do Obsidian → GitHub
1. Na pasta do seu vault:
   ```powershell
   cd C:\caminho\do\seu\vault
   git init
   git add .
   git commit -m "vault inicial"
   ```
2. Crie um repo **privado** no GitHub (ex.: `vault`) e faça o push (o GitHub te dá os comandos exatos).
3. Crie um **PAT fine-grained**: GitHub → *Settings* → *Developer settings* → *Personal access tokens*
   → **Fine-grained tokens** → *Generate*. Escopo: **só esse repositório**, permissão **Contents: Read and write**.
   Guarde o token.

### 2.3 Chave de modelo (o cérebro)
- **https://console.anthropic.com** → *API keys* → crie uma chave. **Defina um limite de gasto** em
  *Billing/Limits* (trava de segurança). (Alternativa: uma chave de router tipo OpenRouter.)

### 2.4 Telegram (o canal de aviso)
1. No Telegram, fale com **@BotFather** → `/newbot` → dê nome e username → ele te dá o **bot token**.
2. Mande qualquer mensagem pro seu bot, depois pegue seu **chat_id**:
   ```powershell
   Invoke-RestMethod "https://api.telegram.org/botSEU_BOT_TOKEN/getUpdates"
   ```
   procure `"chat":{"id":<NÚMERO>}` — esse número é o `owner_chat_id`.

✔️ **Fase 2 pronta quando:** você tem em mãos — ClickUp token + 4 IDs · repo do vault + PAT ·
model key (com limite) · bot token + chat_id. **Nada disso num repo ou colado em chat.**

---

## 🖥️ FASE 3 — VPS + Hermes (~uma tarde)

> Hermes é novo (~4 meses) — confirme os comandos contra os docs vivos:
> https://github.com/nousresearch/hermes-agent . Se ele brigar, o fallback é LibreChat + o cutuca (RUNBOOK).

1. **VPS:** contrate um Ubuntu 22.04 pequeno (Hetzner/DigitalOcean/Contabo, US$5–10/mês). Conecte por SSH.
   Mantenha **isolado do ConsigVerse**.
2. **Instalar o Hermes** (curl, conforme os docs) e rodar a CLI uma vez pra ver o agente responder.
3. **Modelo + Telegram:** configure a model key (com limite) e conecte o **gateway do Telegram** com o bot token.
4. **MCP:** conecte **ClickUp MCP** (tasks) e **GitHub MCP** (vault, com o PAT). Menos privilégio possível.
5. **Profiles:** crie `Tarefas`, `Notas`, `Leitura`.
6. **Skill de lembrete:** configure o cron `reminder-digest` (regras em `development/REMINDER-SKILL-SPEC.md`).
7. **(Opcional agora) BFF no VPS:** rode o BFF ao lado do Hermes (systemd + Caddy pra HTTPS).

✔️ **Fase 3 pronta quando (teste decisivo):** pelo Telegram/Hermes você consegue
"liste minhas tasks de Saúde" e "cria em Trabalho: cobrar Ana sexta" e vê refletir no ClickUp.

---

## 🔗 FASE 4 — Ligar tudo (o "flip", ~15 min)

1. No `.env` do **BFF**:
   ```
   HERMES_MOCK=false
   HERMES_BASE_URL=http://localhost:8080     # ou a URL do Hermes no VPS
   HERMES_API_KEY=<a chave do Hermes>
   ```
2. Confirme os "pontos de solda" (onde o mock vira real), marcados com `TODO`:
   - `bff/app/hermes_client.py` → o endpoint/shape real do Hermes pro `/capture`.
   - `bff/app/tasks.py` → a listagem real de tarefas por área via Hermes/ClickUp MCP.
3. **Push real:** aponte o cron do Hermes pra bater no BFF quando calcular o digest —
   `POST /internal/run-digest` (ou `/internal/notify`). Aí o push do app passa a ser de verdade.

✔️ **Pronto:** app aponta pro Hermes real; tarefas vêm do ClickUp; o digest da manhã chega no
Telegram **e** como push no app. Sem tocar no código do app — só trocou o `.env`.

---

## 🔒 Segurança (faça antes de qualquer uso real)
- [ ] `cd bff; copy .env.example .env` e troque **APP_PASSWORD**, **JWT_SECRET** (string longa) e **INTERNAL_TOKEN**.
- [ ] Limite de gasto na model key.
- [ ] Nada de `.env`, tokens ou service-account no git (já estão no `.gitignore`).

## Ordem sugerida (resumo)
**Hoje:** Fase 0. **Essa semana:** Fase 1 (se quer push) e começar a Fase 2. **Depois:** Fase 3 → Fase 4.

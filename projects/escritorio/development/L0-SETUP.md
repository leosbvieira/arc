---
artifact: setup-runbook
capability: escritorio-app
status: baseline
scope: L0 (encanamento app ↔ BFF ↔ Hermes-mock + push de teste)
---

# L0-SETUP — passo a passo (rodar o cockpit em mock, sem VPS)

Objetivo do L0: **logar no app Android → capturar texto → ver a resposta (mock do Hermes) → e
receber um push de teste no celular.** Tudo local; o Hermes/VPS entram depois.

Pré-requisitos já verificados nesta máquina: Node 24, npm 11, Python 3.12, git. Falta: o app
**Expo Go** no seu Android (Play Store) — e, pro push, uma conta Expo grátis.

---

## 1) Subir o BFF (FastAPI, modo mock)
```powershell
cd projects/escritorio/bff
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
#   (se a rede interceptar TLS, como no cutuca:)
# .venv\Scripts\python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

copy .env.example .env
#   edite .env: APP_PASSWORD, JWT_SECRET, INTERNAL_TOKEN (valores seus)

.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
**Prove it:** abra `http://localhost:8000/health` → `{"ok":true,"mock":true}`.

Descubra o IP da máquina na rede (o app vai usar): `ipconfig` → o `IPv4` (ex.: `192.168.0.10`).
Confirme que o celular alcança: no navegador do celular, `http://SEU_IP:8000/health`.
(Se não abrir: libere a porta 8000 no Firewall do Windows pra rede privada.)

---

## 2) Rodar o app (captura funciona já, no Expo Go)
```powershell
cd projects/escritorio/app
npm install
npx expo install --fix
#   edite src/api.ts → BFF_URL = "http://SEU_IP:8000"
npx expo start
```
No Android: **Expo Go** → escaneie o QR (mesmo Wi-Fi).

**Prove it (captura):** logue com o `APP_PASSWORD` → digite "cobrar Ana sexta" → Enviar →
aparece `[mock:Leitura] anotado: cobrar Ana sexta`. O encanamento app→BFF→(mock)Hermes está vivo.

---

## 3) Conta Expo + projectId (pré-requisito do push)
```powershell
cd projects/escritorio/app
npm install -g eas-cli
eas login          # cria/entra numa conta Expo grátis
eas init           # cria o projeto EAS e preenche o projectId no app.json
```

---

## 4) Dev build (o push remoto NÃO roda no Expo Go)
```powershell
eas build --profile development --platform android
```
Isso gera um APK/AAB de desenvolvimento (build na nuvem da Expo, grátis no free tier). Instale-o
no celular e rode `npx expo start --dev-client` (em vez do Expo Go).

**Prove it (registro):** ao logar no dev build, o app pede permissão de notificação e registra o
Expo push token no BFF. Confirme no BFF: a resposta de `/devices` mostra `count: 1`.

---

## 5) Disparar um push de teste (do lado servidor)
Com o token registrado (passo 4), simule o que o cron do Hermes fará:
```powershell
$body = @{ title = "Escritório"; body = "🔔 cobrança de teste" } | ConvertTo-Json
Invoke-RestMethod -Method Post http://localhost:8000/internal/notify `
  -Headers @{ "X-Internal-Token" = "troque-token-interno" } `
  -ContentType application/json -Body $body
```
**Prove it (push):** a notificação **"🔔 cobrança de teste"** aparece no Android. L0 fechado. ✅

---

## Depois do L0
- **Trilha engine:** RUNBOOK estágios 0–5 (ClickUp Spaces, vault no GitHub, VPS+Hermes, MCP,
  profiles, skill `reminder-digest`). Aí no `.env` do BFF: `HERMES_MOCK=false` + URL + chave, e
  confirme o endpoint real em `bff/app/hermes_client.py`.
- **Trilha app (L1):** tela Tarefas (por área + recência), Capturar-Leitura, e o cron do Hermes
  chamando `/internal/notify` de verdade. Ver `APP-WORK-PACK.md`.

## Troubleshooting
- **App não fala com o BFF:** `BFF_URL` está com o IP certo? (não `localhost`); BFF subiu com
  `--host 0.0.0.0`? Firewall liberou a 8000?
- **`expo start` reclama de versão:** rode `npx expo install --fix`.
- **Push não chega:** você está no **dev build** (não Expo Go)? Deu permissão? `/devices` tem
  `count ≥ 1`? Alguns Androids (Xiaomi/Oppo) matam background — libere a bateria pro app. Lembre:
  o backbone confiável de aviso é o **Telegram**; o push do app é reforço.

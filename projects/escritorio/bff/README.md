# bff — escritório (FastAPI)

Orquestrador determinístico single-user do Aeternum: autentica o app, persiste filas/ritos em
SQLite, chama o Hermes CLI apenas para propor estrutura, e executa escritas aprovadas no
ClickUp, vault GitHub e Google Calendar. Push é o canal primário; Telegram é fallback.

Hermes e tarefas rodam em **mock** por padrão. Em modo real, toda escrita canônica continua
no BFF: o modelo propõe; código idempotente valida e escreve.

## Rodar (Windows PowerShell)

```powershell
cd projects/escritorio/bff
python -m venv .venv
# rede normal (lock com hashes = exatamente o que a suíte e o CI validaram):
.venv\Scripts\python -m pip install --require-hashes -r requirements.lock
# pra rodar os testes: requirements-dev.lock no lugar de requirements.lock
# regenerar os locks depois de mexer em requirements*.txt:
#   uv pip compile requirements.txt --generate-hashes --universal --python-version 3.11 -o requirements.lock
#   uv pip compile requirements.txt requirements-dev.txt --generate-hashes --universal --python-version 3.11 -o requirements-dev.lock
# se a rede intercepta TLS (como no cutuca), use:
# .venv\Scripts\python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

copy .env.example .env    # edite APP_PASSWORD, JWT_SECRET, INTERNAL_TOKEN
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`--host 0.0.0.0` deixa o celular (mesmo Wi-Fi) alcançar. Descubra o IP da máquina com `ipconfig`
(ex.: `192.168.0.10`) — é ele que vai no `BFF_URL` do app.

## Endpoints principais
- `GET  /health` → `{ok, mock}`
- `POST /auth/login` `{password}` → `{token}`
- `POST /capture` (Bearer) `{text, profile?, client_key?, sensivel?}` → enfileira Raw/classificação
- `/reading/sessions*` → buffer recuperável, autosave, compile e descarte de leitura
- `/routines`, `/abertura`, `/shutdown`, `/review/*`, `/objetivos` → ritos e scorecard
- `/agenda`, `/temas`, `POST /agenda/google-calendar` → agenda ICS + escrita GCal aprovada
- `/aprendizados`, `/anki/*`, `/triagem*` → edificação, cards e triagem assistida
- `POST /devices` (Bearer) `{token}` → registra o Expo push token
- `POST /internal/notify` (header `X-Internal-Token`) `{body, kind?, sensivel?}` → push/fallback

## Teste rápido (sem o app)
```powershell
# login
$t = (Invoke-RestMethod -Method Post http://localhost:8000/auth/login -ContentType application/json -Body '{"password":"troque-esta-senha"}').token
# capturar
Invoke-RestMethod -Method Post http://localhost:8000/capture -Headers @{Authorization="Bearer $t"} -ContentType application/json -Body '{"text":"cobrar Ana sexta"}'
```

## Ativação real

No `.env`, configure `HERMES_MOCK=false`, `TASKS_SOURCE=clickup`, PAT do vault, tokens de
notificação e, se usar escrita GCal, o OAuth refresh token. Veja `.env.example`. Push/STT exigem
dev build EAS; o módulo STT é carregado opcionalmente para o app continuar abrindo antes dele.

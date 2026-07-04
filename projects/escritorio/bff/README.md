# bff — escritório (FastAPI)

Vidro fino sobre o Hermes: **auth single-user + proxy `/capture` + relay de push**. Não roda LLM,
não fala com ClickUp/GitHub (isso é o Hermes). Roda em **mock** por padrão, então sobe sem o VPS.

## Rodar (Windows PowerShell)

```powershell
cd projects/escritorio/bff
python -m venv .venv
# rede normal:
.venv\Scripts\python -m pip install -r requirements.txt
# se a rede intercepta TLS (como no cutuca), use:
# .venv\Scripts\python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

copy .env.example .env    # edite APP_PASSWORD, JWT_SECRET, INTERNAL_TOKEN
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`--host 0.0.0.0` deixa o celular (mesmo Wi-Fi) alcançar. Descubra o IP da máquina com `ipconfig`
(ex.: `192.168.0.10`) — é ele que vai no `BFF_URL` do app.

## Endpoints
- `GET  /health` → `{ok, mock}`
- `POST /auth/login` `{password}` → `{token}`
- `POST /capture` (Bearer) `{text, profile?}` → `{reply}`
- `POST /devices` (Bearer) `{token}` → registra o Expo push token
- `POST /internal/notify` (header `X-Internal-Token`) `{title?, body}` → dispara push

## Teste rápido (sem o app)
```powershell
# login
$t = (Invoke-RestMethod -Method Post http://localhost:8000/auth/login -ContentType application/json -Body '{"password":"troque-esta-senha"}').token
# capturar
Invoke-RestMethod -Method Post http://localhost:8000/capture -Headers @{Authorization="Bearer $t"} -ContentType application/json -Body '{"text":"cobrar Ana sexta"}'
```

## Ligar o Hermes de verdade (depois)
No `.env`: `HERMES_MOCK=false`, `HERMES_BASE_URL`, `HERMES_API_KEY`. Confirmar o endpoint/shape
real contra os docs do Hermes em `hermes_client.py`.

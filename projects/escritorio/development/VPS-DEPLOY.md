---
artifact: vps-deploy-runbook
capability: escritorio-engine
status: baseline
scope: mover o escritório (Hermes + BFF) do PC local para um VPS always-on, e ligar o app no real
authored: 2026-07-04
secrets: NENHUM segredo aqui — só a ordem dos passos. Tokens só no servidor.
---

# VPS-DEPLOY — o escritório always-on

Objetivo: sair de "Hermes no PC do Leo (só liga quando o PC está ligado)" para "Hermes + BFF num
VPS 24/7", com o app do celular funcionando **de qualquer lugar** e o **digest da manhã** disparando
sozinho.

> **Verdade dura antes de começar:** a migração re-faz a auth que já funciona local. No VPS (headless,
> sem navegador) o **OAuth do ChatGPT** e o **OAuth do ClickUp** viram fricção. Por isso este runbook
> troca ambos por **credenciais headless-friendly**: modelo via **ANTHROPIC_API_KEY**, ClickUp via
> **token pk_** (servidor MCP por npx). O vault (github_vault) já usa token — copia igual.
>
> **Alternativa 10x mais barata (considere):** deixar o **PC ligado 24/7** + Telegram. Isso já dá
> always-on + acesso de qualquer lugar, com **zero migração**. O VPS vale se você não quer o PC ligado
> o tempo todo ou quer independência total. Se topar o VPS, siga abaixo.

---

## Pré-requisitos (você provê)
- [ ] **VPS Ubuntu 22.04+** pequeno (1 vCPU / 1–2 GB, ~US$5–7/mês). Isolado do ConsigVerse. Acesso SSH.
- [ ] **Domínio** (ou subdomínio) apontando pro IP do VPS — pro HTTPS do app. (Opcional: sem domínio dá
      pra usar só o IP, mas o app pede HTTPS pra push/token; recomendo um subdomínio barato.)
- [ ] **ANTHROPIC_API_KEY** (já temos, validada) — ou aceitar trocar por OpenAI, decidir no Estágio B.
- [ ] **ClickUp token** `pk_…` novo (Settings → Apps) — o pessoal, headless.
- [ ] **GitHub PAT** do vault (o mesmo `github_pat_…`, escopado em `leosbvieira/aeternum`).
- [ ] **Model spend cap** ligado no console da Anthropic.

---

## Estágio A — Subir o VPS (seu)
1. Provisiona o VPS (Hetzner CX22 / DigitalOcean / Vultr — qualquer um serve).
2. `ssh root@IP`, cria usuário não-root, firewall: libera **22 (SSH), 80, 443**. Nada mais.
3. Aponta o domínio (registro A) pro IP.
4. Me dá acesso (ou roda os comandos que eu passo) e a gente segue do Estágio B.

## Estágio B — Hermes no VPS
1. Instala o Hermes (curl conforme docs: github.com/nousresearch/hermes-agent). Confirma `hermes` roda.
2. Copia a config que já funciona: leva o `config.yaml`, `SOUL.md` e a pasta de personalities do PC
   (`%LOCALAPPDATA%\hermes\`) pro `~/.hermes/` do VPS. As 4 personalities + os 10 modos vêm juntos.
3. **Modelo (headless):** no `config.yaml`, `model.provider: anthropic` + `model.default: claude-sonnet-5`,
   e `ANTHROPIC_API_KEY=…` no `~/.hermes/.env`. (Sem OAuth, sem navegador — funciona direto.)
4. **ClickUp (headless):** troca o server `clickup` de OAuth hosted para stdio por token:
   `command: npx` · `args: [-y, @taazkareem/clickup-mcp-server]` · `env: { CLICKUP_API_KEY: <pk_>, CLICKUP_TEAM_ID: 9007178855 }`.
5. **Vault:** copia o server `github_vault` igual (token no `env:`).
6. **API server do Hermes (pro BFF falar com ele):** `API_SERVER_ENABLED=true` + `API_SERVER_KEY=<gera-uma>`
   no `.env`. Anota a key — vira `HERMES_API_KEY` do BFF.
7. `/reload-mcp` + teste: "liste minhas tasks de Saúde" e "anexa em 1- Inbox/teste: ok".

## Estágio C — BFF no VPS
1. `git`/scp do `projects/escritorio/bff` pro VPS. `python -m venv .venv && .venv/bin/pip install -r requirements.txt`.
2. `.env` do BFF: `HERMES_MOCK=false` · `HERMES_BASE_URL=http://localhost:<porta-api-hermes>` ·
   `HERMES_API_KEY=<a key do B.6>` · `APP_PASSWORD`, `JWT_SECRET`, `INTERNAL_TOKEN` (strings longas).
3. Implementar os TODOs reais (eu faço, é código): `bff/app/tasks.py` (`list_by_area`/`create`/`complete`/
   `run_digest`) e confirmar o shape do `hermes_client.capture`. Decisão de arquitetura no fim deste doc.
4. `systemd` unit `escritorio-bff.service` → `uvicorn app.main:app --host 127.0.0.1 --port 8000`. Enable + start.

## Estágio D — HTTPS (Caddy)
1. `apt install caddy`. `/etc/caddy/Caddyfile`:
   ```
   escritorio.SEU-DOMINIO.com {
     reverse_proxy 127.0.0.1:8000
   }
   ```
2. `systemctl reload caddy`. Caddy pega o cert Let's Encrypt sozinho. Testa `https://escritorio.SEU-DOMINIO.com/health`.

## Estágio E — Ligar o app
1. No app (`projects/escritorio/app/src/api.ts`), troca `BFF_URL` pro `https://escritorio.SEU-DOMINIO.com`.
   Agora funciona **de qualquer rede** (não é mais IP local).
2. Rebuild do dev build (EAS) e instala no celular. Push via Expo já funciona pelo domínio.

## Estágio F — Digest da manhã (o motivo do always-on)
1. Cron do Hermes 08:00 America/Sao_Paulo → `POST http://localhost:8000/internal/run-digest`
   (header `X-Internal-Token`). O BFF calcula a cadência (cadence.py, regras do cutuca) e faz o push +
   manda no Telegram. Roda 2× no dia → cada tarefa cobrada 1× (dedupe).

---

## Decisão de arquitetura do `tasks.py` (pra eu implementar o flip)
O app precisa de **lista estruturada** de tarefas. Hermes devolve texto livre (frágil de parsear). Duas opções:
- **(recomendado) BFF → ClickUp REST direto** pra tela de Tarefas (estruturado, confiável, filtra pelos 4
  list_id). Desvia do "glass sobre Hermes" (D-1), mas é muito mais robusto pra dado estruturado.
- **BFF → Hermes** pra **captura** (onde a inteligência importa): texto → Hermes (`capturas`) → nota no vault.

Ou seja: **Tarefas = ClickUp direto; Captura = via Hermes.** Fechar isso antes de escrever o código.

## O que ainda precisa de você (resumo)
VPS provisionado + SSH · domínio (A record) · ClickUp token `pk_` novo · confirmar troca do modelo pra
Anthropic API key · o resto (config, BFF, Caddy, systemd, código do flip) eu preparo/executo.

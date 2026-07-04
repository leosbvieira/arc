---
artifact: bringup-runbook
capability: escritorio-engine
status: baseline
scope: subir o Hermes no VPS e ligar o app real (plano cheio) — RUNBOOK estágios 1–6 + flip
secrets: NENHUM segredo neste arquivo — só IDs (não sigilosos). Tokens vão no env do Hermes no VPS.
---

# HERMES-BRINGUP — subir o engine (nosso setup, concreto)

Transforma o `RUNBOOK.md` genérico nos passos reais do escritório, com os valores confirmados.
Cada estágio tem um **✔️ Prove it** — não avance sem passar. Se o Hermes brigar até o Estágio 3,
**pare e vá pro fallback** (LibreChat + cutuca) — ele tem ~4 meses e é o maior risco do plano.

> **Copiloto:** rode os comandos no VPS via `! <comando>` aqui pra eu ver a saída e te guiar.

## Config confirmada (ClickUp)
- Workspace: `9007178855` · Space: **Personal** (`90133461895`)
- Listas por área (folderless):
  | Área | list_id |
  |---|---|
  | Trabalho | `901327729093` |
  | Finanças | `901327729095` |
  | Saúde | `901327729097` |
  | Pessoal | `901327729099` |

## Pré-requisitos (Fase 2 — os 4 segredos, guardados com segurança)
- [ ] **ClickUp token** `pk_…` (REGENERADO — o que foi colado no chat está queimado)
- [ ] **GitHub PAT** fine-grained (repo do vault, Contents R/W)
- [ ] **Model key** (Anthropic/router) **com limite de gasto**
- [ ] **Telegram** bot token + teu `chat_id`

---

## Estágio 1 — VPS + Hermes de pé
- [ ] VPS Ubuntu pequeno (US$5–10/mês), isolado do ConsigVerse. SSH.
- [ ] Instalar o Hermes (curl, conforme docs: https://github.com/nousresearch/hermes-agent).
- [ ] Rodar a CLI uma vez.

**✔️ Prove it:** `hermes` inicia e responde localmente.

## Estágio 2 — Modelo + Telegram (o alcance)
- [ ] Configurar o provider do modelo (a model key, com o spend cap ativo).
- [ ] Ligar o gateway do **Telegram** (bot token). `/start` no teu celular.

**✔️ Prove it:** você manda mensagem pro bot e ele responde.

## Estágio 3 — MCP: ClickUp + GitHub (o make-or-break)
- [ ] **ClickUp MCP** com o `pk_…` (menos privilégio possível).
- [ ] **GitHub MCP** com o PAT (só o repo do vault).

**✔️ Prove it (decisivo, com as nossas listas):**
- "liste minhas tasks de **Saúde**" → volta a lista `901327729097` do ClickUp.
- "cria em **Trabalho**: cobrar Ana o relatório sexta" → aparece na lista `901327729093`.
- "anexa em `Leituras/Sapiens.md`: cap 3 fraco" → commit no repo do vault.

> Passou o Estágio 3 → o Hermes já é ~90% do escritório. Doeu aqui → fallback, sem teimar.

## Estágio 4 — Profiles (os "agentes")
- [ ] **Tarefas** — lane de tarefas: conhece as 4 listas (IDs acima), cria/lista/conclui, cadência-aware.
- [ ] **Notas** — lane do vault: anexa/recupera notas via GitHub MCP.
- [ ] **Leitura** — aplica a CAPTURE-GRAMMAR (6 modos, ver `CAPTURE-GRAMMAR-SPEC.md`) → nota do dia no vault.

**✔️ Prove it:** trocar de profile muda o comportamento/ferramentas; `/v1/models` lista os 3.

## Estágio 5 — Lembrete + push (D-14)
Abordagem recomendada (reusa o código testado do cutuca que já está no BFF):
- [ ] **Cron do Hermes** (08:00 America/Sao_Paulo, ver `REMINDER-SKILL-SPEC.md`) → só dispara um
      `POST http://localhost:8000/internal/run-digest` (server-to-server, header `X-Internal-Token`).
- [ ] O **BFF** (`run_digest` real) busca as tarefas via Hermes, aplica a cadência (`cadence.py`,
      regras do cutuca) e faz o **push** (Expo) + o Hermes manda o mesmo digest no Telegram.

Assim o "cérebro" da cadência fica no BFF (validado, 50 testes) e o Hermes é o provedor de dados.
Alternativa: encodar a cadência como skill do Hermes (mais fiel ao spec, mais trabalho).

**✔️ Prove it:** rodar 2× no dia → cada task cobrada 1× (dedupe), tom escala, chega no Telegram **e** como push no app.

## Estágio 6 — Batch de fim de dia (need #5)
- [ ] Cron do Hermes (linguagem natural): "fechamento do dia — releia tarefas por área + notas do dia,
      consolide, proponha amanhã."

**✔️ Prove it:** mensagem noturna resumindo o dia.

---

## Fase 4 — O flip (ligar o app no real, ~15 min)
1. `.env` do **BFF** (no VPS): `HERMES_MOCK=false`, `HERMES_BASE_URL`, `HERMES_API_KEY`.
2. Preencher os `TODO` reais:
   - `bff/app/hermes_client.py` → endpoint/shape real do Hermes pro `/capture` (confirmar contra os docs vivos).
   - `bff/app/tasks.py` → `list_by_area`/`create`/`complete`/`run_digest` reais via Hermes (usando os 4 list_id acima).
3. Deploy do BFF ao lado do Hermes (systemd + Caddy HTTPS) e apontar o app (`BFF_URL`) pro domínio.

**✔️ Pronto:** app mostra tarefas reais do ClickUp por área; digest da manhã chega no Telegram + push; captura vira nota no vault. Sem mexer no código do app — só `.env` + os TODOs.

## Fallback (se o Hermes brigar)
LibreChat (cockpit web) + o `../cutuca` rodando o cron de lembrete — mesmas fontes, mesmas decisões.
O app continua igual (glass); só troca quem está atrás do BFF.

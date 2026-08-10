---
artifact: plano-de-migracao
capability: escritorio
status: proposto
date: 2026-08-06
decide: "tirar o BFF do PC do Leo para os ritos pararem de depender de ele estar logado"
---

# Plano — tirar o Aeternum do PC

## O número que motiva

```
últimos 30 dias · 11 dias com ZERO notificação (37%)
quando dispara, entrega 100% (85 push + 11 telegram, todos entregue=1)
```

O problema nunca foi entrega. É que **o scheduler não roda**: as 6 tarefas
(`Toque 05:30`, `Check-in 08:20`, `Jornal 08:30`, `Digest 09:00`, `Shutdown 19:00`,
`Fechamento 21:00`) são Scheduled Tasks do Windows, e o BFF sobe com `-AtLogOn`.
PC desligado ou deslogado = sistema mudo.

E o padrão é perverso: os dias mudos são justamente os dias em que ele se afastou —
que são exatamente os dias em que o lembrete importaria.

## O nó: seis funções dependem de um `.exe` local

`hermes_client` roda `subprocess.run(hermes.exe -z)`. Quem chama:

| função | quem usa |
|---|---|
| `classify` | fila de captura (todo item capturado) |
| `propose_triage` | triagem automática |
| `compile_reading` | nota de leitura |
| `suggest_anki` | cards |
| `draft_diario` | rascunho do fechamento |
| `chat` | o Mentor |

**Mas o que sangra não passa por nenhuma delas.** Verificado no código: os endpoints
`/internal/nudge` e `/internal/run-digest` — os únicos que as 6 tarefas agendadas
chamam — têm **zero** referência a `hermes_client`. Só `/closing` toca (o rascunho do
diário, que é opcional).

Ou seja: **dá para consertar os 37% sem resolver o Hermes.**

## Sobre levar o Hermes junto

> **Revisado em 10/ago/2026.** A versão anterior desta seção dizia que rodar o OAuth de
> um IP de datacenter era "convite a bloqueio de conta". **Isso não se sustentou na
> verificação** — a correção está abaixo, junto com o risco real, que é outro e mais
> provável.

Investigado em `%LOCALAPPDATA%\hermes`:

- **Modelo é por API, não local.** `provider: openai-codex`,
  `base_url: https://chatgpt.com/backend-api/codex`. Não precisa de GPU nem RAM
  grande — um VPS de €4/mês roda.
- **A credencial é OAuth da conta pessoal dele.** `auth.json` guarda
  `access_token` + `refresh_token` do ChatGPT, com refresh automático.
- 2,2 GB em disco. Tem `Dockerfile` e `docker-compose.yml` próprios.

### O que a pesquisa desmentiu

- O caso que mais parecia bloqueio — [openai/codex#11743](https://github.com/openai/codex/issues/11743),
  literalmente *"Stream disconnected on VPS using ChatGPT OAuth"*, Ubuntu, IP de
  datacenter — é **bug de streaming do CLI**. O login funcionou, `curl` no mesmo
  endpoint respondeu, e reproduziu em duas versões. Conta nenhuma foi tocada.
- Existem guias de instalação em VPS headless (SSH port-forward do `localhost:1455`) e
  a própria OpenAI shippou **device-code auth** para máquinas sem navegador. Não se
  constrói isso para um caso de uso que se quer punir.
- O material alarmista sobre suspensão vem quase todo de **empresas que vendem relay de
  API** (qcode.cc, teamorouter, 4sAPI) e termina recomendando o serviço delas. É
  marketing fantasiado de aviso. A versão anterior deste doc reproduziu isso.
- Perguntada diretamente sobre uso programático e server-side em
  [openai/codex#8338](https://github.com/openai/codex/discussions/8338), a OpenAI
  respondeu *"I'm an engineer, not a lawyer"* e apontou os Termos genéricos. **Não há
  regra pública dizendo que pode nem que não pode** — é zona cinzenta, o que significa
  que pode mudar sem aviso, não que hoje seja proibido.
- Os gatilhos que essas fontes descrevem (muitas pessoas numa conta, frota de bots numa
  assinatura, troca rápida de região/VPN) **não descrevem o Leo**: uma pessoa, uma
  conta, um IP fixo, um punhado de chamadas por dia.

*Ressalva:* as páginas de ToS da OpenAI retornam 403 para fetch automatizado, então o
texto da cláusula não foi lido diretamente.

### O risco real: colisão de refresh token

`hermes_cli/auth.py:3672` trata um caso específico:

```
"Codex refresh token was already consumed by another client
 (e.g. Codex CLI or VS Code extension).
 Run `codex` in your terminal to generate fresh tokens,
 then run `hermes auth` to re-authenticate."
```

O Leo **usa o `codex` CLI direto** para trabalho pesado. Hermes e Codex CLI dividem o
mesmo refresh token, e **quem refresca primeiro consome o do outro.** Isso derruba o
Aeternum de verdade, exige intervenção manual, e ele reproduz sozinho no próprio PC —
sem VPS, sem IP de datacenter, sem ban nenhum.

**E isso piora no servidor:** refresh token consumido numa máquina headless significa
SSH com port-forward para reautenticar. É o argumento mais forte a favor de trocar o
provider para `ANTHROPIC_API_KEY` (que já está preenchida no `.env` do Hermes): **API
key não tem refresh, então não há o que consumir.**

### A Fase 2 não devolve o Mentor

Registrado porque o plano original deixava implícito e leva a decisão errada: o worker
que "puxa trabalho do VPS" conserta o **assíncrono** — `classify`, `compile_reading`,
`suggest_anki`, `propose_triage`. O **Chat é síncrono** (`main.py`, rota `/chat` →
`hermes_client.chat` → `_oneshot`): com o PC desligado não há o que puxar, e o Leo fica
olhando o spinner. **Mentor 24/7 só existe com o Hermes fora do PC.**

### Recomendação revisada

Levar o Hermes na fase 1 com o OAuth atual **não é imprudente** — as opções voltam à
mesa. Mas se o objetivo inclui o Mentor de qualquer lugar, o caminho é **Hermes no VPS
com `ANTHROPIC_API_KEY`**, e por dois motivos que nunca tiveram a ver com bloqueio:

1. **Isolamento de quota.** A cota do plano ChatGPT é uma janela rolante compartilhada:
   um Aeternum 24/7 classificando toda captura come do mesmo balde que ele usa para
   programar. Uma API key é orçamento separado e medido.
2. **Modo de falhar melhor.** 429 com `Retry-After` é uma espera. OAuth expirado num
   servidor headless é uma manutenção manual.

Custos assumidos: passa a pagar por token (com spend cap), e o Mentor troca de modelo
(`gpt-5.4` → `claude-sonnet-5`) — o `SOUL.md` e as personalities vão junto, mas o jeito
da resposta muda.

### Já implementado (10/ago)

O Hermes distingue cota de credencial desde o PR #33168 (`CODEX_RATE_LIMITED_CODE`,
`relogin_required=False`, `Retry-After` parseado) — conferido presente na instalação
local, commit `a653bb0`. Mas o BFF reduzia **toda** falha a `RuntimeError("hermes_error")`
→ `502 hermes_indisponivel`, e essa distinção morria no stderr do subprocesso.

Corrigido sem ferir a lei 7 (**código de erro não é conteúdo**): `hermes_client.HermesFalhou`
carrega um código de lista fechada — `hermes_quota`, `hermes_credencial`, `hermes_error` —
e o `/chat` devolve `503` + `Retry-After` nos dois primeiros. O app traduz em
`src/chatError.ts`. Agora "a cota acabou, volta em ~2 min" e "o PC pode estar desligado"
são frases diferentes na tela.

## Fases

### Fase 1 — parar de sangrar
BFF + banco sobem. Hermes fica no PC.

Passa a rodar 24/7, independente do PC: os 6 nudges, os lembretes agendados, o
digest, a fila de captura (etapa do Raw), o backup automático, e todos os ritos
(abertura, shutdown, fechamento, review, rotinas, pontos, melhorias).

Degrada enquanto o PC está desligado: `classify` (a captura vira `nota` e fica no
Raw — comportamento que o código **já** tem hoje quando o Hermes falha), Mentor,
compilar leitura, sugerir Anki, triagem automática. Nenhum perde dado: a lei 1
grava o Raw verbatim **antes** de qualquer processamento.

### Fase 2 — a IA volta, sem expor a conta
Um worker no PC **puxa** trabalho do VPS (polling), roda o Hermes localmente e
devolve o resultado. Puxar, não receber: evita IP fixo, NAT e porta aberta na casa
dele. A `capture_queue` já tem exatamente essa forma — `pending → claim → done` com
backoff — então é reaproveitamento, não invenção.

### Fase 3 — opcional
Hermes no VPS, só se ele quiser trocar o provider para API key própria.

## O que migra

| item | como |
|---|---|
| `data.db` (208 KB) | cópia via API online do SQLite (o backup novo já produz exatamente isso) |
| segredos | **recriados no servidor**, nunca copiados. É a hora de rotacionar tudo |
| 6 Scheduled Tasks | viram `systemd timers` (ou cron), com o mesmo horário e o mesmo fuso |
| `start-bff.ps1` | vira unit do systemd com `Restart=always` |

## Itens técnicos que não podem ser esquecidos

1. **HTTPS é obrigatório.** Hoje o app fala com o BFF por `http` na LAN. Pela
   internet precisa de TLS — Android bloqueia cleartext por padrão. Caddy resolve
   com uma linha (certificado automático).
2. **Fuso.** `tz.py` fixa `America/Sao_Paulo` no código, então o horário dos ritos
   não depende do relógio do servidor. Bom — mas o `TZ` do sistema deve ir junto
   assim mesmo, para os logs baterem.
3. **O `.env` do BFF tem `DB_PATH` relativo.** Já ancorado no código hoje
   (`f147bb9`), mas no servidor vale usar caminho absoluto explícito.
4. **CORS e `internal_token`.** `/internal/*` fica exposto à internet. Confirmar que
   o token protege e considerar bind local + chamada pelo próprio host.

## Rollback

Barato de propósito: a tela de **Ajustes** do app já deixa trocar a URL do BFF. Se
o VPS der problema, é um campo de texto — volta para o PC. O BFF local continua
instalado, só desabilitado. E o banco tem backup diário desde hoje.

## Decisões que dependem do Leo

1. **Provedor.** Sugestão: Hetzner CX22 (~€4/mês, 2 vCPU / 4 GB). Alternativa sem
   custo: Oracle Free Tier (mais burocracia, menos previsível).
2. **Domínio.** Precisa de um nome para o TLS. Pode ser um subdomínio de algo que
   ele já tenha.
3. **Rotacionar os segredos agora?** `APP_PASSWORD` e `JWT_SECRET` ficaram expostos
   em terminal em 06/08, e o PAT do vault é emprestado. A migração é o momento
   natural de trocar os três de uma vez.
4. **O Hermes vai junto, e com qual provider?** (nova, 10/ago) Três saídas:
   **(A)** Hermes fica no PC — Mentor só com o PC ligado, custo zero;
   **(B)** Hermes no VPS com o OAuth atual — Mentor 24/7, sem custo novo, mas herda a
   colisão de refresh token com o `codex` CLI dele e a manutenção fica por SSH;
   **(C)** Hermes no VPS com `ANTHROPIC_API_KEY` — Mentor 24/7, quota isolada, sem
   refresh para colidir; paga por token e o Mentor troca de modelo.
   O que decide é se ele aceita pagar por token e trocar o modelo — **não** risco de
   bloqueio, que foi verificado e não se sustentou.

## Aceite da fase 1

- [ ] PC desligado por 24h e os 6 nudges chegaram no horário
- [ ] captura pelo celular com o PC desligado: Raw no vault, item na fila, sem perda
- [ ] fechamento do dia gravado com o PC desligado
- [ ] backup diário nascendo no servidor
- [ ] trocar a URL nos Ajustes volta tudo para o PC em menos de 1 minuto

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

### DECISÃO (10/ago/2026): opção B — Hermes no VPS com o OAuth atual

O Leo escolheu **B**, contra a recomendação C abaixo. O que B entrega: **Mentor 24/7**,
**custo novo zero** e o Mentor **continua no `gpt-5.4`** — o modelo a que ele se
acostumou, que era um custo real da opção C e não aparecia em nenhuma planilha.

O que ele aceita junto, registrado para não virar surpresa: a colisão de refresh token,
a manutenção da credencial num servidor, e uma zona cinzenta que pode mudar sem aviso.

**O risco que é só do B — e que decide se B é viável:** o único problema técnico
documentado com esta configuração exata (VPS + IP de datacenter + OAuth do ChatGPT) é
[openai/codex#11743](https://github.com/openai/codex/issues/11743) — *stream disconnected
before completion*. O issue está fechado sem resolução visível. Não é bloqueio de conta,
mas **quebra o Mentor do mesmo jeito**. Por isso ele vira o **primeiro passo**, e não uma
descoberta no meio da migração (ver "Ordem de execução do B").

#### O achado que barateia o B

`hermes_cli/auth.py` mostra que o Hermes tem **device-code OAuth para `openai-codex`**
(`hermes auth add openai-codex`, fonte `manual:device_code`) e **suporta credenciais
independentes**:

> *"Manual entries whose tokens never matched the singleton represent INDEPENDENT
> accounts added via `hermes auth add openai-codex` and must not be overwritten by a
> re-auth that targeted a different account (regression for #39236)."*

Duas consequências práticas:

1. **Login headless não precisa de SSH port-forward.** O device code imprime um código,
   ele aprova no navegador do celular. O `_print_loopback_ssh_hint` é para provedores de
   redirect em loopback (xAI, Spotify) — não para o codex.
2. **NÃO copiar `auth.json` para o VPS.** `config.yaml`, `SOUL.md` e as personalities
   vão; **tokens não**. Uma autorização device-code nova no VPS gera a própria cadeia de
   refresh, e é assim que a colisão com o `codex` CLI do PC deixa de existir — a colisão
   acontece quando dois clientes dividem o **mesmo** token, não quando usam a mesma
   conta por autorizações separadas.

O ponto 2 é **provável, não provado**: o texto do Hermes fala de "contas independentes",
e a inferência para "mesma conta, autorizações separadas" vem de como a rotação de
refresh token funciona em OAuth, não de um teste. Está na ordem de execução como gate.

#### Ordem de execução do B

Os dois primeiros passos são baratos e podem **matar a opção B antes** de qualquer
migração — que é exatamente o que se quer deles.

1. **Provisionar o VPS e instalar só o Hermes.** Mandar um prompt. Se der *stream
   disconnected* (#11743), B está bloqueado e a decisão volta para a mesa com um fato
   novo, não com uma teoria.
2. **`hermes auth add openai-codex` no VPS, via device code.** Sem copiar `auth.json`.
   Depois: usar o `codex` CLI no PC e, em seguida, falar com o Mentor pelo celular.
   Repetir por alguns dias. Se os dois continuarem vivos, as cadeias são independentes e
   a colisão está resolvida por construção.
3. Config do Hermes (`config.yaml`, `SOUL.md`, personalities) + MCP ClickUp headless
   (token `pk_`) + MCP do vault (token igual).
4. BFF + banco (Estágio C), Caddy/HTTPS (Estágio D), crons (Estágio F).

**Automação (2026-10-11):** os passos 1, 3 (instalação do Hermes, sem o login) e 4 (BFF,
unit, Caddy, firewall) estão em `ops/vps-install.sh`, ensaiado do zero num container
Ubuntu 24.04 antes do corte. O script gera `APP_PASSWORD`/`JWT_SECRET`/`INTERNAL_TOKEN`
novos no VPS (nenhum segredo do PC viaja), deixa o serviço **habilitado mas parado** e
imprime o que continua manual: `hermes auth add openai-codex --no-browser` como o usuário
do serviço (passo 2 acima), `CLICKUP_TOKEN`/`GITHUB_PAT`/`TELEGRAM_*` no `bff.env`, e o
snapshot do banco (`ops/release-backup-rollback.md`). O BFF recusa subir com
`TASKS_SOURCE=clickup` sem token e com segredo de exemplo — de propósito.

**Nota técnica:** o `VPS-DEPLOY.md` manda ligar o API server do Hermes (`API_SERVER_ENABLED`)
para o BFF falar com ele. **Isso está obsoleto:** o `hermes_client` de hoje não usa HTTP,
ele sobe `hermes -z` como subprocesso. Com BFF e Hermes na mesma máquina, isso continua
valendo — e `_hermes_python()` já procura `python.exe` **e** `python`, então o caminho é
Linux-ready. O que importa é `hermes` estar no PATH do usuário que roda o BFF.
`HERMES_BASE_URL` e `HERMES_API_KEY` viraram vestígio.

### Recomendação revisada (histórico — não escolhida)

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
4. ~~**O Hermes vai junto, e com qual provider?**~~ **DECIDIDO (10/ago): opção B** —
   Hermes no VPS com o OAuth atual. Mentor 24/7, custo novo zero, `gpt-5.4` preservado.
   Detalhe, riscos e ordem de execução na seção "DECISÃO (10/ago/2026)" acima.
   Fica **um gate**: o #11743 (*stream disconnected* em VPS com OAuth) tem que ser
   testado antes de migrar qualquer coisa. Se falhar, a decisão volta com um fato novo.

## Aceite da fase 1

- [ ] PC desligado por 24h e os 6 nudges chegaram no horário
- [ ] captura pelo celular com o PC desligado: Raw no vault, item na fila, sem perda
- [ ] fechamento do dia gravado com o PC desligado
- [ ] backup diário nascendo no servidor
- [ ] trocar a URL nos Ajustes volta tudo para o PC em menos de 1 minuto

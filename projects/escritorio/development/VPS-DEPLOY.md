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

## Estado real (desde 2026-10-11)

O escritório roda num VPS desde o corte de 11/out/2026. Esta seção é a verdade de operação;
o que vem depois dela ("Histórico") é o plano de julho, guardado como mapa.

Este repositório é **público**: IP, nome DNS e provedor não entram aqui — estão no painel do
provedor. Nos comandos abaixo aparecem como `<vps>` e `<dominio>`.

### O que existe no servidor

| O quê | Onde |
| --- | --- |
| Sistema | Ubuntu 24.04, 2 vCPU / 8 GB, **um disco só**. Relógio em **UTC**: o fuso do Leo mora no código (`bff/app/tz.py`) e escrito nos timers |
| Checkout do monorepo | `/opt/escritorio/src` |
| Releases do BFF | `/opt/escritorio/releases/<commit>/bff` (código + `.venv`); `current` aponta a última instalada |
| Estado | `/var/lib/escritorio-bff/`: `data.db`, `backups/` (14 dias, feitos pelo próprio BFF), `hermes-home/` (HOME do Hermes) |
| Segredos | `/etc/escritorio/bff.env` (root 0600) |
| Serviço | `escritorio-bff.service`: uvicorn em `127.0.0.1:8000`, usuário `escritorio-bff` |
| HTTPS | Caddy: `<dominio>` → `127.0.0.1:8000`, certificado automático |
| Ritos | `escritorio-rito-<slug>.timer` → `escritorio-rito@.service` → `/usr/local/sbin/escritorio-rito` |
| Backup fora do VPS | `escritorio-backup.timer` → `/usr/local/sbin/escritorio-backup` → repositório git privado |
| Rede | ufw: só 22, 80 e 443. `unattended-upgrades` ligado |

### Como chegou lá

`ops/vps-install.sh` faz o que eram os Estágios B–D (pacotes, usuário, release com lock de
hashes, Hermes, units, Caddy, ufw) e é idempotente. Ficou manual, e continua manual numa
reinstalação:

1. **Login do Hermes no Codex** por device code, como o usuário do serviço (o instalador
   imprime os comandos). O `auth.json` nunca é copiado de outra máquina.
2. **Segredos** no `bff.env`: `CLICKUP_TOKEN`, `GITHUB_PAT`, `TELEGRAM_*` e a `APP_PASSWORD`.
   Colados direto no servidor — nunca em chat, nunca em commit.
3. **O banco**: snapshot pela API do SQLite e hash conferido na cópia
   (`ops/release-backup-rollback.md`).

O BFF fala com o ClickUp por REST e com o vault pela API do GitHub; o Hermes é só o modelo
(`hermes -z` por subprocesso). Não há servidor MCP nem API server do Hermes: os passos B.3–B.6
e C.2 do histórico não valem mais.

O app aponta pro servidor pela tela de Ajustes (ou por `EXPO_PUBLIC_BFF_URL` no perfil do
`eas.json`, num build novo).

### Operar

```
ssh root@<vps>
systemctl status escritorio-bff
journalctl -u escritorio-bff -n 100 --no-pager
curl -fsS http://127.0.0.1:8000/health          # de fora: https://<dominio>/health
systemctl list-timers 'escritorio-*'
systemctl --failed
```

### Nova release

```
git -C /opt/escritorio/src fetch -q origin
git -C /opt/escritorio/src checkout -q main
git -C /opt/escritorio/src merge -q --ff-only origin/main
# Roda uma CÓPIA: o instalador mexe no checkout e não pode se trocar debaixo de si mesmo.
cp /opt/escritorio/src/projects/escritorio/ops/vps-install.sh /root/vps-install.sh
bash /root/vps-install.sh                       # sem DOMAIN: o Caddyfile fica como está
```

O instalador monta a release nova, regrava as units e os timers e **não reinicia o BFF**.
Antes do restart, conferir que a fila de captura não tem item em curso — a release nova
escreveria no vault e no ClickUp antes de qualquer validação
(`ops/release-backup-rollback.md`, "Ativar uma release", passo 3):

```
sqlite3 "file:/var/lib/escritorio-bff/data.db?mode=ro" \
  "SELECT status, count(*) FROM capture_queue GROUP BY status"
systemctl start escritorio-backup.service       # o banco de agora fora do VPS, antes de trocar o código
systemctl restart escritorio-bff && sleep 3 && curl -fsS http://127.0.0.1:8000/health
journalctl -u escritorio-bff -n 30 --no-pager   # sem traceback
```

Voltar o código (o banco fica): as releases anteriores continuam em
`/opt/escritorio/releases/`.

```
sed -i 's|releases/<nova>/|releases/<anterior>/|g' /etc/systemd/system/escritorio-bff.service
systemctl daemon-reload && systemctl restart escritorio-bff
```

### Ritos (os avisos do dia)

A fonte única dos horários é `bff/ritos.json`. No PC quem disparava era o Agendador do
Windows (`bff/scripts/sync-cron.ps1`); no VPS são timers do systemd gerados do mesmo arquivo
(`python -m app.ritos`, chamado pelo instalador). O corte de 11/out esqueceu esta peça:
entre 11 e 12/out o servidor não avisou nada.

- **Mudar um horário:** editar `ritos.json`, release nova, instalador. Rito que sai do
  arquivo tem o timer removido.
- **Ver:** `systemctl list-timers 'escritorio-rito-*'` e `journalctl -t escritorio-rito -n 30`.
  O journal guarda só o veredito (`HTTP 200 "push":true ...`), nunca o texto do aviso.
- **Testar o encanamento sem avisar ninguém:** `systemctl start escritorio-rito@nudge-toque.service`
  fora da hora do toque. O journal mostra `"skipped":"atrasado"`: token aceito, corpo aceito,
  nada enviado. **Não** teste com `digest-digest`: o digest não tem janela e sai na hora.
- **Silenciar tudo:** `systemctl disable --now $(cd /etc/systemd/system && ls escritorio-rito-*.timer)`.
  O instalador religa todos na próxima release; pra calar um rito de vez, ele sai do
  `ritos.json`.
- A janela (90 min de atraso, 5 de adiantamento), o dedupe do dia e a reserva do slot ficam
  no BFF (`ritos.atrasado`, `notif_reserva`): disparar duas vezes é seguro.
  `Persistent=false` é de propósito — rito perdido num reboot não é recuperado, porque aviso
  atrasado é pior que aviso nenhum.
- BFF fora do ar na hora do rito: o disparador espera 60 s pelo `/health` e depois falha;
  aparece em `systemctl --failed`.

### Backup fora do VPS

O backup diário do próprio BFF (`backups/data-<dia>.db`) mora no mesmo disco do banco. O que
cobre a perda do disco é o `escritorio-backup.timer`: todo dia às 06:30 UTC (03:30 em São
Paulo) tira um snapshot pela API online do SQLite, confere com `integrity_check` e empurra
`data.db` + `SHA256SUMS` + `MANIFESTO.txt` (quando, release, contagem por tabela) pra um
repositório git **privado**. Cada commit é um dia. Se falhar, o Leo recebe um aviso no
Telegram e a unit aparece em `systemctl --failed`.

Vai **só o banco**. De propósito, não vão:

- `bff.env`: segredo não mora em repositório, nem privado. Perdeu o disco, recria — a senha
  do app, tokens novos no ClickUp e no GitHub, o token do bot no BotFather.
- o HOME do Hermes: é instalação mais o `auth.json`, que nunca sai da máquina. Perdeu o
  disco, é `vps-install.sh` e um login novo por device code.

Preparo (uma vez; refazer numa reinstalação). O timer só liga se o `backup.env` existir:

```
# 1. Repositório PRIVADO e vazio no GitHub.
# 2. No VPS, uma chave de deploy que só existe ali:
ssh-keygen -q -t ed25519 -N "" -C escritorio-backup@vps -f /etc/escritorio/backup_deploy_key
cat /etc/escritorio/backup_deploy_key.pub
#    colar em Settings → Deploy keys do repositório, COM "Allow write access".
# 3. Chave de host do GitHub fixada, vinda por TLS (não um ssh-keyscan no escuro):
curl -fsS https://api.github.com/meta \
  | python3 -c 'import json,sys; [print("github.com", k) for k in json.load(sys.stdin)["ssh_keys"]]' \
  > /etc/escritorio/backup_known_hosts
ssh-keygen -lf /etc/escritorio/backup_known_hosts   # conferir com os fingerprints em docs.github.com
# 4. Destino:
echo 'BACKUP_REMOTE=git@github.com:<dono>/<repo-privado>.git' > /etc/escritorio/backup.env
chmod 0600 /etc/escritorio/backup*
# 5. Instalador de novo (liga o timer) e a primeira rodada à mão:
bash /root/vps-install.sh
systemctl start escritorio-backup.service && journalctl -u escritorio-backup -n 5 --no-pager
```

Restaurar, num computador com acesso ao repositório:

```
git clone git@github.com:<dono>/<repo-privado>.git && cd <repo-privado>
sha256sum -c SHA256SUMS
sqlite3 data.db "PRAGMA integrity_check"
cat MANIFESTO.txt
# um dia anterior: git log --oneline   e   git show <commit>:data.db > data.db
```

Daí em diante é o `ops/release-backup-rollback.md` ("Rollback", passo 3): restaurar o banco
perde o que veio depois do snapshot e **não** desfaz o que já foi pro ClickUp, pro vault e
pras notificações.

### SSH

Só chave: `/etc/ssh/sshd_config.d/00-escritorio-hardening.conf` com
`PasswordAuthentication no`, `KbdInteractiveAuthentication no` e
`PermitRootLogin prohibit-password`. O nome começa com `00-` porque no sshd vale a
**primeira** ocorrência de cada opção, e a imagem do provedor traz um `50-cloud-init.conf`
com a senha ligada. Conferir o efeito: `sshd -T | grep -i -E 'passwordauth|permitroot'`.

Perdeu a chave do PC: console pelo navegador no painel do provedor, e a chave pública nova
em `/root/.ssh/authorized_keys`.

### Atualizações do sistema

`unattended-upgrades` aplica as correções sozinho, mas não reinicia. Se
`/var/run/reboot-required` existir: `reboot` numa hora sem rito. BFF, Caddy e timers voltam
sozinhos — conferir com `systemctl is-active escritorio-bff caddy` e o `/health` de fora.

### Pendências conhecidas

- Rate limit por IP sem orçamento agregado; o shutdown cancela os workers sem drenar
  (revisão Codex 2026-10-11, #3 e #6).
- Rito que falha só aparece em `systemctl --failed`: não há aviso ativo de "BFF fora do ar".
- Sem fail2ban. Com a senha desligada, a força bruta no SSH é só ruído de log.
- O relógio do sistema é UTC, então o journal sai em UTC.

---

## Histórico: o plano de julho de 2026

Daqui pra baixo é o plano original, mantido como mapa dos estágios. Onde ele diz
"candidato" ou "nenhum executado num VPS", leia como julho/setembro: o que está em `ops/`
roda em produção desde o corte.

> **Verdade dura antes de começar:** a migração re-faz a auth que já funciona local. No VPS (headless,
> sem navegador) o **OAuth do ChatGPT** e o **OAuth do ClickUp** viram fricção. Por isso este runbook
> troca ambos por **credenciais headless-friendly**: modelo via **ANTHROPIC_API_KEY**, ClickUp via
> **token pk_** (servidor MCP por npx). O vault (github_vault) já usa token — copia igual.
>
> **Alternativa 10x mais barata (considere):** deixar o **PC ligado 24/7** + Telegram. Isso já dá
> always-on + acesso de qualquer lugar, com **zero migração**. O VPS vale se você não quer o PC ligado
> o tempo todo ou quer independência total. Se topar o VPS, siga abaixo.
>
> **Atualização 2026-10-11:** a decisão foi a opção B do `VPS-PLANO.md` — Hermes no VPS
> com o **OAuth do Codex por device code** (não `ANTHROPIC_API_KEY`), e o BFF chama o
> Hermes por subprocesso (`hermes -z`), não pelo API server. Os Estágios B–D abaixo estão
> automatizados em `ops/vps-install.sh`; este arquivo fica como mapa dos estágios e do que
> continua manual (login do Hermes, tokens, snapshot do banco, crons do Estágio F).

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
1. `git`/scp do `projects/escritorio/bff` pro VPS. `python -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.lock`.
2. `.env` do BFF: `HERMES_MOCK=false` · `HERMES_BASE_URL=http://localhost:<porta-api-hermes>` ·
   `HERMES_API_KEY=<a key do B.6>` · `APP_PASSWORD`, `JWT_SECRET`, `INTERNAL_TOKEN` (strings longas).
3. Implementar os TODOs reais (eu faço, é código): `bff/app/tasks.py` (`list_by_area`/`create`/`complete`/
   `run_digest`) e confirmar o shape do `hermes_client.capture`. Decisão de arquitetura no fim deste doc.
4. `systemd` unit `escritorio-bff.service` → `uvicorn app.main:app --host 127.0.0.1 --port 8000`. Enable + start.
   Candidatos prontos em `ops/`: `escritorio-bff.service` (hardening, HOME do Hermes, TimeoutStopSec
   acima do HERMES_TIMEOUT), `bff.env.example` (formato EnvironmentFile) e `release-backup-rollback.md`
   (backup pela API do SQLite, verificação antes de religar o cron, rollback de código sem voltar o banco).
   Portados do ramo `local-2026-09` em 12/09/2026; nenhum executado num VPS ainda.

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

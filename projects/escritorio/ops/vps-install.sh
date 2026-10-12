#!/usr/bin/env bash
# Instala o Escritório BFF + Hermes CLI num Ubuntu 24.04 limpo. Idempotente: rodar de
# novo atualiza a release e preserva banco, segredos e o HOME do Hermes.
#
# Uso (como root, no VPS):
#   REPO_URL=https://github.com/leosbvieira/arc.git DOMAIN=escritorio.exemplo.com \
#     bash vps-install.sh
# Ou com um checkout já presente:  SRC_DIR=/src bash vps-install.sh
#
# Variáveis:
#   SRC_DIR    checkout do monorepo (default: clona REPO_URL em /opt/escritorio/src)
#   REPO_URL   usado só se SRC_DIR não existir
#   REF        branch/tag/commit a instalar (default: main)
#   DOMAIN     nome DNS pro Caddy/TLS (vazio = Caddy não é configurado)
#   ENSAIO=1   container sem systemd: pula enable/start, ufw e o serviço do Caddy
#
# Layout (ops/escritorio-bff.service):
#   /opt/escritorio/releases/<id>/bff   código + .venv, imutável por release
#   /var/lib/escritorio-bff/            data.db, backups/, hermes-home/ (HOME do Hermes)
#   /etc/escritorio/bff.env             segredos (root:root 0600)
#   /usr/local/sbin/escritorio-backup   cópia do banco pra fora do VPS (timer diário);
#                                       só liga com /etc/escritorio/backup.env (VPS-DEPLOY.md)
#   /usr/local/sbin/escritorio-rito     dispara um rito no BFF local; os timers
#                                       escritorio-rito-<slug>.timer saem de bff/ritos.json
#
# O que este script NÃO faz, de propósito: o login do Hermes no Codex (device code,
# exige você: `hermes auth add openai-codex` como o usuário do serviço) e copiar o
# auth.json de outra máquina (VPS-PLANO.md: nunca).
set -euo pipefail

SRC_DIR="${SRC_DIR:-/opt/escritorio/src}"
REPO_URL="${REPO_URL:-https://github.com/leosbvieira/arc.git}"
REF="${REF:-main}"
DOMAIN="${DOMAIN:-}"
ENSAIO="${ENSAIO:-0}"

SVC_USER=escritorio-bff
STATE=/var/lib/$SVC_USER
HERMES_HOME=$STATE/hermes-home
RELEASES=/opt/escritorio/releases
ENV_FILE=/etc/escritorio/bff.env
UNIT=/etc/systemd/system/escritorio-bff.service

log() { printf '\n==> %s\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "rode como root"; exit 1; }

log "pacotes"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl git sqlite3 rsync openssl gnupg sudo libatomic1 \
  python3 python3-venv python3-pip systemd tzdata ufw >/dev/null

if ! command -v caddy >/dev/null; then
  log "caddy (repo oficial)"
  curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy >/dev/null
fi

log "usuário e diretórios"
id -u $SVC_USER >/dev/null 2>&1 || useradd --system --home-dir "$STATE" --shell /usr/sbin/nologin $SVC_USER
install -d -m 0700 -o $SVC_USER -g $SVC_USER "$STATE" "$STATE/backups" "$HERMES_HOME"
install -d -m 0700 -o root -g root /etc/escritorio
install -d -m 0755 "$RELEASES"

log "código ($REF)"
if [ ! -d "$SRC_DIR/.git" ]; then
  git clone -q "$REPO_URL" "$SRC_DIR"
fi
if [ -z "${SRC_READONLY:-}" ] && [ -w "$SRC_DIR/.git" ]; then
  git -C "$SRC_DIR" fetch -q origin && git -C "$SRC_DIR" checkout -q "$REF" \
    && { git -C "$SRC_DIR" merge -q --ff-only "origin/$REF" 2>/dev/null || true; }
fi
RELEASE_ID="$(git -C "$SRC_DIR" rev-parse --short=12 HEAD)"
REL="$RELEASES/$RELEASE_ID"
echo "release: $RELEASE_ID"

if [ ! -x "$REL/bff/.venv/bin/python" ]; then
  log "release $RELEASE_ID: venv + lock com hashes"
  install -d "$REL"
  rsync -a --delete \
    --exclude .venv --exclude '__pycache__' --exclude '.env' --exclude 'data.db*' \
    --exclude backups --exclude '*.db' --exclude .pytest_cache \
    "$SRC_DIR/projects/escritorio/bff/" "$REL/bff/"
  python3 -m venv "$REL/bff/.venv"
  "$REL/bff/.venv/bin/python" -m pip install -q --upgrade pip
  "$REL/bff/.venv/bin/python" -m pip install -q --require-hashes -r "$REL/bff/requirements.lock"
  chown -R root:root "$REL"; chmod -R a+rX "$REL"
fi
ln -sfn "$REL" "$RELEASES/current"

log "hermes (como $SVC_USER, HOME=$HERMES_HOME)"
HERMES_BIN="$(runuser -u $SVC_USER -- env HOME="$HERMES_HOME" bash -c 'command -v hermes || ls "$HOME"/.local/bin/hermes 2>/dev/null' || true)"
if [ -z "$HERMES_BIN" ]; then
  runuser -u $SVC_USER -- env HOME="$HERMES_HOME" PATH="$HERMES_HOME/.local/bin:$PATH" \
    bash -c 'curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash'
  HERMES_BIN="$(runuser -u $SVC_USER -- env HOME="$HERMES_HOME" bash -c 'ls "$HOME"/.local/bin/hermes 2>/dev/null || ls "$HOME"/.hermes/venvs/*/bin/hermes 2>/dev/null | head -1')"
fi
[ -n "$HERMES_BIN" ] || { echo "hermes não encontrado depois do instalador"; exit 1; }
echo "hermes: $HERMES_BIN"
runuser -u $SVC_USER -- env HOME="$HERMES_HOME" "$HERMES_BIN" --version | head -1

if [ ! -f "$ENV_FILE" ]; then
  log "segredos novos em $ENV_FILE (preencha ClickUp, PAT, Telegram depois)"
  sed -e "s|^APP_PASSWORD=.*|APP_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)|" \
      -e "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" \
      -e "s|^INTERNAL_TOKEN=.*|INTERNAL_TOKEN=$(openssl rand -hex 32)|" \
      -e "s|^DB_PATH=.*|DB_PATH=$STATE/data.db|" \
      -e "s|^HERMES_BIN=.*|HERMES_BIN=$HERMES_BIN|" \
      "$SRC_DIR/projects/escritorio/ops/bff.env.example" | tr -d '\r' > "$ENV_FILE"   # CR de checkout Windows quebra o EnvironmentFile
  chmod 0600 "$ENV_FILE"
fi

log "unit systemd (release $RELEASE_ID)"
sed -e "s|__RELEASE_ID__|$RELEASE_ID|g" \
    -e "s|^Environment=PATH=.*|Environment=PATH=$(dirname "$HERMES_BIN"):/usr/local/bin:/usr/bin:/bin|" \
    "$SRC_DIR/projects/escritorio/ops/escritorio-bff.service" > "$UNIT"
systemd-analyze verify "$UNIT" || true

log "backup fora do VPS: script + timer"
OPS="$SRC_DIR/projects/escritorio/ops"
install -m 0755 "$OPS/escritorio-backup.sh" /usr/local/sbin/escritorio-backup
install -m 0644 "$OPS/escritorio-backup.service" "$OPS/escritorio-backup.timer" /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/escritorio-backup.service || true

log "ritos: disparador + timers gerados de ritos.json"
install -m 0755 "$OPS/escritorio-rito.sh" /usr/local/sbin/escritorio-rito
install -m 0644 "$OPS/escritorio-rito@.service" /etc/systemd/system/
RITOS_TMP="$(mktemp -d)"
RITO_TIMERS="$(cd "$REL/bff" && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m app.ritos "$RITOS_TMP" | tr '\n' ' ')"
[ -n "$RITO_TIMERS" ] || { echo "ritos.json não gerou nenhum timer"; exit 1; }
# Reconcilia como o sync-cron.ps1: rito renomeado ou removido do ritos.json não pode
# deixar o timer antigo disparando ao lado do novo.
for velho in /etc/systemd/system/escritorio-rito-*.timer; do
  if [ -e "$velho" ] && [ ! -e "$RITOS_TMP/$(basename "$velho")" ]; then
    [ "$ENSAIO" = 1 ] || systemctl disable --now "$(basename "$velho")" || true
    rm -f "$velho"
    echo "rito removido: $(basename "$velho")"
  fi
done
install -m 0644 "$RITOS_TMP"/escritorio-rito-*.timer /etc/systemd/system/
rm -rf "$RITOS_TMP"
systemd-analyze verify /etc/systemd/system/escritorio-rito-*.timer || true

if [ -n "$DOMAIN" ]; then
  log "caddy: $DOMAIN -> 127.0.0.1:8000"
  cat > /etc/caddy/Caddyfile <<CADDY
$DOMAIN {
	encode gzip
	request_body {
		max_size 8MB
	}
	reverse_proxy 127.0.0.1:8000
}
CADDY
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
fi

if [ "$ENSAIO" = 1 ]; then
  log "ENSAIO=1: sem systemctl/ufw. Pronto."
  exit 0
fi

log "firewall: só 22, 80, 443"
ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

log "serviços"
systemctl daemon-reload
# Só habilita: o BFF recusa subir com TASKS_SOURCE=clickup e CLICKUP_TOKEN vazio
# (guard do boot), então o start fica pra depois de preencher o env.
systemctl enable escritorio-bff.service
[ -n "$DOMAIN" ] && systemctl reload caddy || true
# O destino do backup (repositório + chave de deploy) é decisão do Leo: sem o
# backup.env o timer fica instalado e desligado, e a unit nem tenta rodar.
if [ -f /etc/escritorio/backup.env ]; then
  systemctl enable --now escritorio-backup.timer
else
  echo "backup fora do VPS: sem /etc/escritorio/backup.env, timer DESLIGADO (VPS-DEPLOY.md)"
fi
# Os ritos (toque, check-in, jornal, digest, shutdown, fechamento, review): sem estes
# timers nada chama /internal/* e o servidor fica mudo — foi o que o corte de 11/out
# esqueceu. Ligam sempre; o restart é pra hora nova do ritos.json valer já. Com o BFF
# parado (primeira instalação, antes dos segredos) o rito falha e aparece em
# `systemctl --failed`, que é o aviso certo.
# shellcheck disable=SC2086
systemctl enable $RITO_TIMERS
# shellcheck disable=SC2086
systemctl restart $RITO_TIMERS

if systemctl is-active --quiet escritorio-bff.service; then
  cat <<FIM

Release $RELEASE_ID instalada. O serviço AINDA roda a anterior até reiniciar:
  systemctl restart escritorio-bff && sleep 3 && curl -fsS http://127.0.0.1:8000/health
Antes do restart, conferir a fila de captura: ops/release-backup-rollback.md,
"Ativar uma release", passo 3.
FIM
  exit 0
fi
cat <<FIM

Instalado (serviço habilitado, ainda PARADO). Falta você:
  1. Login do Hermes no Codex (device code):
       runuser -u $SVC_USER -- env HOME=$HERMES_HOME $HERMES_BIN auth add openai-codex --type oauth --no-browser
     e apontar o provedor:
       runuser -u $SVC_USER -- env HOME=$HERMES_HOME $HERMES_BIN config set model.provider openai-codex
       runuser -u $SVC_USER -- env HOME=$HERMES_HOME $HERMES_BIN config set model.default gpt-5.5
       runuser -u $SVC_USER -- env HOME=$HERMES_HOME $HERMES_BIN config set model.base_url https://chatgpt.com/backend-api/codex
  2. Preencher em $ENV_FILE: CLICKUP_TOKEN, GITHUB_PAT, TELEGRAM_*, e HERMES_MOCK=false.
     Depois: systemctl start escritorio-bff && sleep 3 && curl -fsS http://127.0.0.1:8000/health
     (sem CLICKUP_TOKEN o serviço cai no boot de propósito — veja journalctl -u escritorio-bff)
  3. Se o banco vem do PC: parar o serviço, copiar o snapshot pra $STATE/data.db
     (chown $SVC_USER), subir de novo. Roteiro: ops/release-backup-rollback.md.
  4. Backup fora do VPS: criar a chave de deploy e o /etc/escritorio/backup.env
     (development/VPS-DEPLOY.md, "Backup fora do VPS") e rodar este script de novo.
Os timers dos ritos já estão ligados (systemctl list-timers 'escritorio-rito-*'):
enquanto o serviço estiver parado eles falham, e é esperado.
FIM

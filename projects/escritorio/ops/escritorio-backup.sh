#!/usr/bin/env bash
# Cópia do banco do BFF para FORA do VPS: um repositório git privado.
#
# Por quê: o backup diário do próprio BFF (`backups/data-<dia>.db`) mora no mesmo disco
# do banco, e num VPS de um disco só `BACKUP_DIR_2` não tem outro volume pra apontar.
# Se o disco morre, banco e backups morrem juntos (release-backup-rollback.md, passo 1
# de "Antes de qualquer troca de versão"; revisão Codex 2026-10-11, #2).
#
# O que vai: SÓ o banco (`data.db`), o hash e um manifesto com as contagens.
# O que NÃO vai, de propósito:
#   - /etc/escritorio/bff.env   segredo não mora em repositório, nem privado;
#   - ~/.hermes/auth.json       VPS-PLANO.md: nunca sai da máquina;
#   - o resto do HOME do Hermes é instalação, não estado: `vps-install.sh` e um login
#                               por device code refazem.
#
# Roda como root pelo timer (escritorio-backup.timer). A chave de deploy é do root e não
# do usuário do serviço: quem comprometer o BFF não alcança o histórico do backup. Só o
# snapshot é tirado COMO o usuário do serviço, pela API online do SQLite — o BFF segue
# escrevendo, e root abrindo um banco WAL vivo é o jeito de deixar -wal/-shm com dono
# errado.
#
# Preparo (uma vez só) e restauração: development/VPS-DEPLOY.md, "Backup fora do VPS".
set -euo pipefail
umask 077

CONF="${BACKUP_CONF:-/etc/escritorio/backup.env}"
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

SVC_USER="${SVC_USER:-escritorio-bff}"
DB="${BACKUP_DB:-/var/lib/escritorio-bff/data.db}"
WORK="${BACKUP_WORK:-/var/lib/escritorio-backup}"
KEY="${BACKUP_KEY:-/etc/escritorio/backup_deploy_key}"
KNOWN="${BACKUP_KNOWN_HOSTS:-/etc/escritorio/backup_known_hosts}"
BRANCH="${BACKUP_BRANCH:-main}"
ENV_BFF="${BACKUP_ENV_BFF:-/etc/escritorio/bff.env}"
REMOTE="${BACKUP_REMOTE:?defina BACKUP_REMOTE em $CONF (ex.: git@github.com:dono/repo.git)}"

# Backup que falha calado é backup que não existe: qualquer saída != 0 vira aviso no
# Telegram do Leo, com o mesmo bot do BFF. Sem Telegram configurado, fica só o journal
# (`systemctl --failed`). O token vai por stdin (-K -) pra não aparecer na lista de
# processos; nada do banco entra na mensagem (lei 7).
avisar() {
  local token chat
  token="$(sed -n 's/^TELEGRAM_BOT_TOKEN=//p' "$ENV_BFF" 2>/dev/null | head -1 | tr -d '"\r')"
  chat="$(sed -n 's/^TELEGRAM_CHAT_ID=//p' "$ENV_BFF" 2>/dev/null | head -1 | tr -d '"\r')"
  [ -n "$token" ] && [ -n "$chat" ] || return 0
  printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$token" \
    | curl -fsS -m 20 -K - --data-urlencode "chat_id=$chat" --data-urlencode "text=$1" \
      >/dev/null 2>&1 || true
}
falhou() {
  local rc=$?
  [ "$rc" -eq 0 ] || avisar "⚠ escritório: o backup fora do VPS falhou (rc=$rc). No servidor: journalctl -u escritorio-backup"
}
trap falhou EXIT

TMP="$WORK/tmp"
REPO="$WORK/repo"
rm -rf "$TMP"
install -d -m 0700 "$WORK" "$TMP"

# 1. Snapshot consistente, com o BFF de pé. O nome não casa com `data-*.db`, então a
#    rotação de 14 dias do BFF nunca o confunde com um backup dela.
SNAP="$(dirname "$DB")/backups/offsite.parcial"
install -d -m 0700 -o "$SVC_USER" -g "$SVC_USER" "$(dirname "$SNAP")"
rm -f "$SNAP"
setpriv --reuid="$SVC_USER" --regid="$SVC_USER" --init-groups -- \
  sqlite3 -batch "$DB" ".timeout 15000" ".backup '$SNAP'"
install -m 0600 -o root -g root "$SNAP" "$TMP/data.db"
rm -f "$SNAP"

# 2. Conferir a CÓPIA antes de publicar: empurrar lixo por cima do último estado bom é
#    pior que não empurrar nada. `immutable=1` lê sem criar -wal/-shm nem tocar no arquivo.
cd "$TMP"
URI="file:$TMP/data.db?immutable=1"
[ -s data.db ] || { echo "snapshot vazio"; exit 1; }
veredito="$(sqlite3 -batch "$URI" "PRAGMA integrity_check")"
[ "$veredito" = ok ] || { echo "integrity_check falhou: $veredito"; exit 1; }

sha256sum data.db > SHA256SUMS   # caminho RELATIVO: o hash se confere na cópia restaurada
{
  echo "quando_utc: $(date -u +%FT%TZ)"
  echo "release: $(basename "$(readlink -f /opt/escritorio/releases/current 2>/dev/null || echo desconhecida)")"
  echo "bytes: $(stat -c %s data.db)"
  echo "sha256: $(cut -d" " -f1 SHA256SUMS)"
  echo "user_version: $(sqlite3 -batch "$URI" "PRAGMA user_version")"
  echo "tabelas:"
  sqlite3 -batch "$URI" \
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name" \
    | while IFS= read -r t; do
        printf '  %s: %s\n' "$t" "$(sqlite3 -batch "$URI" "SELECT count(*) FROM \"$t\"")"
      done
} > MANIFESTO.txt

# 3. Publicar. O ssh só enxerga a chave de deploy e a chave de host fixada (nada de
#    aceitar host novo no escuro); o git não lê config de ninguém.
export GIT_SSH_COMMAND="ssh -F /dev/null -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN -o ConnectTimeout=20"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 HOME="$WORK"

if [ ! -d "$REPO/.git" ]; then
  git init -q -b "$BRANCH" "$REPO"
  git -C "$REPO" remote add origin "$REMOTE"
fi
cd "$REPO"
git remote set-url origin "$REMOTE"

# Partir sempre da ponta do remoto: num VPS reinstalado o repositório local nasce vazio
# e o histórico já existe lá. rc=2 do ls-remote é "a branch ainda não existe" (primeiro
# backup); qualquer outro erro é rede ou chave, e aí é falha de verdade.
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null; then
  git fetch -q origin "$BRANCH"
  git reset -q --hard FETCH_HEAD
else
  rc=$?
  [ "$rc" -eq 2 ] || exit "$rc"
fi

install -m 0600 "$TMP/data.db" "$TMP/SHA256SUMS" "$TMP/MANIFESTO.txt" "$REPO/"
cat > LEIA-ME.md <<'LEIAME'
# Backup do banco do escritório

Gerado no VPS por `ops/escritorio-backup.sh` (repositório `arc`, `projects/escritorio`).
Cada commit é um snapshot do `data.db` do BFF, tirado pela API online do SQLite e com
`integrity_check` conferido antes do push.

- `data.db` é o banco. `SHA256SUMS` é o hash dele. `MANIFESTO.txt` diz quando, de qual
  release e quantas linhas por tabela.
- Um dia anterior: `git log --oneline` e `git show <commit>:data.db > data.db`.
- Restaurar: `sha256sum -c SHA256SUMS`, depois o roteiro
  `ops/release-backup-rollback.md` ("Rollback", passo 3: restaurar o banco é raro e
  não desfaz o que já foi pro ClickUp, pro vault e pras notificações).

Não há segredo aqui: `bff.env` e o `auth.json` do Hermes nunca entram neste repositório.
LEIAME
git add -A
# O manifesto carrega a hora, então uma rodada normal sempre tem o que gravar. Só não
# tem quando roda duas vezes no mesmo segundo, e `git commit` sem mudança sai com 1:
# viraria um aviso de falha falso.
if git diff --cached --quiet; then
  rm -rf "$TMP"
  echo "ok: nada mudou desde o commit $(git rev-parse --short HEAD)"
  exit 0
fi
git -c user.name="escritorio-backup" -c user.email="escritorio-backup@localhost" \
  commit -q -m "backup $(sed -n 's/^quando_utc: //p' MANIFESTO.txt)"
git push -q origin "HEAD:refs/heads/$BRANCH"

rm -rf "$TMP"
echo "ok: commit $(git rev-parse --short HEAD), sha256 $(sed -n 's/^sha256: //p' MANIFESTO.txt)"

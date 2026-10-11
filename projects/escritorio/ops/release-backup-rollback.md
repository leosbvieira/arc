# Roteiro candidato: release, backup e rollback do BFF

Nenhum comando deste roteiro foi executado num VPS. Adaptado do ramo
`local-2026-09` para a arquitetura da nuvem: **um único SQLite** (`DB_PATH`,
default `data.db`), Hermes como **CLI oneshot** (sem servidor, sem ledger
próprio), ClickUp por REST, vault no GitHub, push Expo com Telegram de ponte.
Ler junto: `development/VPS-DEPLOY.md` (o caminho feliz), `ops/escritorio-bff.service`,
`ops/bff.env.example`.

## Inventário — o que existe fora do código

| Estado | Onde | Observação |
| --- | --- | --- |
| Banco do BFF (tudo: fila de captura, leituras, pontos, rotinas, `notif_log`, `notif_reserva`, devices) | `DB_PATH` (+ `-wal`, `-shm` enquanto o processo vive) | Única fonte local de verdade. WAL/SHM fazem parte do banco: nunca apagar "pra destravar". |
| Backup diário 1 | `Path(DB_PATH).parent/backups/data-<dia>.db` | Feito pelo próprio BFF via SQLite Backup API, com `integrity_check` antes; 14 dias. Mesmo volume do banco. |
| Backup diário 2 | `BACKUP_DIR_2` | Mesma rotina, OUTRO volume. Vazio = desligado. |
| Hermes | `$HOME/.hermes` do usuário do serviço (`config.yaml`, `SOUL.md`, personalities, `.env` com chaves, sessões) | Backup separado, cifrado/restrito. Não mora na release. |
| Segredos do BFF | `/etc/escritorio/bff.env` | root 0600. Preservar JWT_SECRET/INTERNAL_TOKEN entre releases salvo rotação planejada (rotação de JWT_SECRET desloga o celular). |
| Efeitos externos | ClickUp (tarefas), vault no GitHub (notas), Expo/Telegram (avisos já entregues) | **Não estão no backup.** Restaurar um banco antigo não os desfaz e pode fazer o BFF repeti-los. |
| App | fila offline, rascunho de leitura, token de push registrado, JWT | Limpar dados/reinstalar NÃO é procedimento de rollback do servidor. |

## Antes de qualquer troca de versão

1. Diretório de backup **novo e privado**, fora de todos os caminhos acima — e **fora do
   disco do VPS**: `BACKUP_DIR_2` nasce vazio no `bff.env.example`, então sem este passo
   banco, `backups/`, `bff.env` e o HOME do Hermes morrem juntos com o disco. Vale um
   `scp`/`rsync` pro PC ou um bucket; o corte pro VPS só acontece depois que uma cópia de
   fora do VPS foi restaurada com sucesso no ensaio abaixo (revisão Codex 2026-10-11, #2).
2. Parar produtores: cron/timers do Hermes que chamam `/internal/*`; o BFF (`systemctl stop`).
   Esperar o stop terminar (até `TimeoutStopSec`): uma captura em curso no Hermes precisa
   acabar. Se o stop estourar o prazo, a fila pode ter item em `processing` — isso é
   **normal** e o worker retoma; não editar a fila à mão.
3. Com o processo parado, copiar o banco pela API do SQLite (não `cp` de um `.db` vivo):
   ```
   sqlite3 /var/lib/escritorio-bff/data.db ".backup '/backup/<dia>/data.db'"
   sqlite3 /backup/<dia>/data.db "PRAGMA integrity_check"
   (cd /backup/<dia> && sha256sum data.db > SHA256SUMS)   # caminho RELATIVO, ver ensaio
   ```
   Guardar junto: hash do release (commit), `pip freeze` do venv, versão do Hermes.
4. Cópia do `bff.env` e do `~/.hermes` (cifradas) no mesmo diretório.

## Ativar uma release

1. Release imutável em `/opt/escritorio/releases/<id>/bff` com venv **criado no destino**
   (`python -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.lock`).
   Nunca mover um venv pronto. Nunca duas releases do BFF rodando ao mesmo tempo (um banco,
   um scheduler, uma reserva de digest).
2. Renderizar a unit trocando `__RELEASE_ID__`; `systemd-analyze verify`; `daemon-reload`.
3. Com o BFF parado (passo anterior), `systemctl start`. O `init_db` aplica migrações
   idempotentes (`CREATE TABLE IF NOT EXISTS` + `ALTER` guardados) — **o schema novo é
   compatível pra frente, não pra trás** (ver rollback).
   **Atenção:** o start já liga o worker de captura e o scheduler, mesmo com os crons
   parados. Se a fila tiver `pending`/`processing`, a release nova escreve no vault e no
   ClickUp antes de qualquer validação — e rollback de código não desfaz isso. Antes de
   subir, conferir no snapshot: `SELECT status, count(*) FROM capture_queue GROUP BY status`;
   com pendência, deixar a release antiga drenar primeiro (revisão Codex 2026-10-11, #5).
4. Verificar antes de religar produtores:
   - `GET /health` via Caddy (HTTPS) e local (`127.0.0.1:8000`);
   - login com o app; `GET /tasks`; `GET /digest` (só leitura);
   - `journalctl -u escritorio-bff` sem traceback;
   - o backup worker escreveu `backups/data-<hoje>.db` (ele roda no boot).
   Não usar uma captura real como probe: ela vira nota no vault e tarefa no ClickUp.
5. Religar cron/timers. O primeiro `/internal/run-digest` do dia respeita `notif_reserva`
   e `notif_log`: se já saiu hoje, responde `skipped`.

## Rollback

1. Parar produtores e o BFF (mesma disciplina de stop).
2. Apontar a unit pra release **anterior** e subir. **Manter o banco atual.** O código
   anterior ignora tabelas/colunas que não conhece (é só `SELECT` com nomes explícitos),
   então um rollback de código normalmente **não** precisa de restauração de dados.
3. Restaurar o banco do backup é uma decisão separada e rara. Ela **perde** tudo que
   aconteceu depois do snapshot e **não** desfaz efeitos externos: capturas já viradas
   nota/tarefa reaparecem como `pending` na fila e seriam reenviadas ao Hermes;
   `notif_reserva`/`notif_log` do dia somem e o digest pode sair de novo. Antes de
   restaurar: `UPDATE capture_queue SET status='done'` para o que já foi entregue (conferir
   no vault/ClickUp) e marcar `notif_log` do dia — ou aceitar a duplicata conscientemente.
4. Se o código anterior não subir com o schema atual (não deve acontecer; se acontecer é
   bug de migração), ficar em manutenção e corrigir **pra frente**, não voltar o banco.

## Ensaio de restauração (antes do corte pro VPS)

Num diretório isolado, com `HERMES_MOCK=true`, `TASKS_SOURCE=mock`, sem `GITHUB_PAT`,
sem Telegram, sem `EXPO_PUSH_URL` alcançável:

```
# 1. restaurar o SNAPSHOT (não um banco vazio) num caminho isolado
cp /backup/<dia>/data.db /tmp/ensaio/data.db
# o hash tem de ser conferido na CÓPIA, não na origem (SHA256SUMS com caminho absoluto
# relia o original e deixa passar uma cópia diferente — revisão Codex 2026-10-11, #7)
(cd /tmp/ensaio && sha256sum -c /backup/<dia>/SHA256SUMS)
# 2. migrar com o código da release NOVA e conferir
DB_PATH=/tmp/ensaio/data.db .venv/bin/python - <<'PY'
import sqlite3
from contextlib import closing
from app import store
from app.config import settings
store.init_db()
with closing(sqlite3.connect(settings.db_path)) as con:
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    for t in ("capture_queue", "reading_sessions", "routine_checks", "notif_log", "devices"):
        print(t, con.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
    print("fila", con.execute("SELECT status, count(*) FROM capture_queue GROUP BY status").fetchall())
PY
```

Provar: o hash confere, o snapshot abre, `integrity_check` = ok, o `init_db` da release
nova migra sem erro e as contagens batem com o manifesto do backup. **Não** use o
`pytest` como prova: o `conftest` troca o `DB_PATH` por um banco temporário, então a suíte
fica verde sem nunca abrir o snapshot. Só então o backup "vale".

## Caddy

`request_body { max_size 8MB }` no site do BFF é a segunda camada acima dos limites
por campo do próprio BFF (`TEXTO_*` em `bff/app/main.py`). Sem nginx: a nuvem usa Caddy.

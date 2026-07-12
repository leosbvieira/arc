"""Persistência local do P1 (sqlite3 síncrono).

Único dono do schema e das conexões. `_connect()` é o helper interno único: toda
conexão nasce em WAL + busy_timeout (worker de captura e endpoints escrevem em
paralelo, então a concorrência é real). `init_db()` aplica o schema inteiro de
forma idempotente e é chamado no startup (main.lifespan).

Higiene (lei 7): `log_event.meta` e `capture_queue.last_error` NUNCA recebem o
conteúdo capturado — só classe/código de erro e metadados sem PII.
"""
import json
import sqlite3
import time
from contextlib import closing
from datetime import date

from .config import settings

# Teto de tentativas da fila de captura. `pending_captures` esconde quem passou
# do teto e `mark_capture(bump_attempts=True)` marca 'failed' ao atingi-lo.
MAX_ATTEMPTS = 5

# Colunas do contrato de fila (Tasks 9/10/12). `status` fica de fora de propósito:
# em `pending_captures` é sempre 'pending', em `failed_captures` sempre 'failed'.
_CAPTURE_COLS = (
    "id, ts, text, profile, client_key, attempts, raw_path, "
    "clickup_task_id, last_error"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
  token TEXT PRIMARY KEY, created REAL
);
CREATE TABLE IF NOT EXISTS routine_checks (
  data TEXT NOT NULL, rotina TEXT NOT NULL, feito INTEGER NOT NULL,
  template TEXT NOT NULL, PRIMARY KEY (data, rotina)
);
CREATE TABLE IF NOT EXISTS routines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  bloco TEXT NOT NULL,
  dias TEXT NOT NULL DEFAULT '*',
  templates TEXT NOT NULL DEFAULT '*',
  passos TEXT NOT NULL DEFAULT '[]',
  ordem INTEGER NOT NULL DEFAULT 0,
  origem TEXT NOT NULL DEFAULT 'leo',
  ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, projeto TEXT,
  categoria TEXT, inicio REAL NOT NULL, fim REAL NOT NULL,
  duracao_s INTEGER NOT NULL, paginas INTEGER, livro TEXT, session_key TEXT
);
CREATE TABLE IF NOT EXISTS telemetry (
  ts REAL NOT NULL, evento TEXT NOT NULL, ref TEXT DEFAULT '', meta_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS notif_log (
  ts REAL NOT NULL, data_local TEXT NOT NULL, evento TEXT NOT NULL,
  canal TEXT NOT NULL, entregue INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS capture_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, text TEXT NOT NULL,
  profile TEXT, client_key TEXT, status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0, raw_path TEXT, clickup_task_id TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS digest_runs (
  data_local TEXT PRIMARY KEY, body TEXT NOT NULL, count INTEGER NOT NULL,
  delivered INTEGER NOT NULL, ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS scheduler (
  id INTEGER PRIMARY KEY AUTOINCREMENT, quando REAL NOT NULL, tipo TEXT NOT NULL,
  ref TEXT NOT NULL, disparado INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS dia (
  data TEXT PRIMARY KEY,
  template TEXT,
  energia TEXT,
  clareza TEXT,
  prioridade_1 TEXT,
  checkin_em REAL
);
CREATE TABLE IF NOT EXISTS shutdown (
  data TEXT PRIMARY KEY,
  prioridades TEXT NOT NULL DEFAULT '[]',
  feito_em REAL
);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(settings.db_path, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def init_db() -> None:
    with closing(_connect()) as con:
        con.executescript(_SCHEMA)

        # Migração idempotente para bancos criados antes do session_key. O índice
        # vem depois do ALTER porque CREATE TABLE IF NOT EXISTS não adiciona coluna.
        session_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(sessions)")
        }
        if "session_key" not in session_columns:
            con.execute("ALTER TABLE sessions ADD COLUMN session_key TEXT")
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_session_key "
            "ON sessions(session_key)"
        )

        # Migração idempotente para bancos criados antes do client_key. O índice
        # vem depois do ALTER porque CREATE TABLE IF NOT EXISTS não adiciona coluna.
        columns = {
            row["name"] for row in con.execute("PRAGMA table_info(capture_queue)")
        }
        if "client_key" not in columns:
            con.execute("ALTER TABLE capture_queue ADD COLUMN client_key TEXT")
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_capture_client_key "
            "ON capture_queue(client_key)"
        )
        con.commit()

    # Semente das rotinas: conexão própria (BEGIN IMMEDIATE não pode nascer dentro
    # da transação do schema) e só num banco vazio — ver _seed_routines.
    _seed_routines()


# --- devices (push tokens) --------------------------------------------------


def add_device(token: str) -> None:
    with closing(_connect()) as con:
        con.execute(
            "INSERT OR REPLACE INTO devices (token, created) VALUES (?, ?)",
            (token, time.time()),
        )
        con.commit()


def list_devices() -> list[str]:
    with closing(_connect()) as con:
        rows = con.execute("SELECT token FROM devices").fetchall()
    return [r[0] for r in rows]


# --- routine_checks ---------------------------------------------------------


def record_checks(data: str, template: str, checks: list[tuple[str, bool]]) -> None:
    with closing(_connect()) as con:
        con.executemany(
            "INSERT OR REPLACE INTO routine_checks (data, rotina, feito, template) "
            "VALUES (?, ?, ?, ?)",
            [(data, rotina, int(feito), template) for rotina, feito in checks],
        )
        con.commit()


def get_checks_since(data_inicio: str) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM routine_checks WHERE data >= ? ORDER BY data, rotina",
            (data_inicio,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_checks_on(data: str) -> dict[str, bool]:
    """{slug: feito} de UM dia — o que a abertura (A1a/A1b) precisa pra dizer o que já
    está marcado. A PK (data, rotina) permite escrita parcial: marcar de manhã e fechar
    à noite convivem na mesma data."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT rotina, feito FROM routine_checks WHERE data = ?", (data,)
        ).fetchall()
    return {r["rotina"]: bool(r["feito"]) for r in rows}


# --- routines (dado editável; P2 item 2) ------------------------------------
# `slug` é a chave ESTÁVEL: é o que vai em routine_checks.rotina e o que amarra o
# histórico do scorecard. Nasce no create e NUNCA é reescrito. Delete é SOFT
# (ativo=0) pelo mesmo motivo: apagar a rotina não pode apagar o passado dela.

# manha < dia < noite; depois `ordem`; depois `id` (desempate estável).
_ROUTINE_ORDER = (
    "CASE bloco WHEN 'manha' THEN 0 WHEN 'dia' THEN 1 ELSE 2 END, ordem, id"
)
_ROUTINE_COLS = "id, slug, nome, bloco, dias, templates, passos, ordem, origem"


def _routine(row: sqlite3.Row) -> dict:
    """Row → dict do contrato: `passos` volta como lista (no banco é JSON)."""
    r = dict(row)
    try:
        passos = json.loads(r.get("passos") or "[]")
    except (TypeError, ValueError):
        passos = []
    r["passos"] = passos if isinstance(passos, list) else []
    return r


def _seed_routines() -> int:
    """Semeia os exemplos SÓ num banco vazio (idempotente; init_db roda a cada boot).

    BEGIN IMMEDIATE serializa o count+insert entre escritores: dois processos subindo
    juntos não podem semear duas vezes (o UNIQUE do slug seguraria, mas aqui a gente
    nem chega lá). Banco já semeado ou com rotinas do Leo → no-op, nunca sobrescreve.
    """
    from .routines import SEED

    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM routines LIMIT 1").fetchone() is not None:
            con.commit()
            return 0
        con.executemany(
            "INSERT INTO routines "
            "(slug, nome, bloco, dias, templates, passos, ordem, origem, ativo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'exemplo', 1)",
            [
                (slug, nome, bloco, dias, templates, json.dumps(passos), i)
                for i, (slug, nome, bloco, dias, templates, passos)
                in enumerate(SEED, start=1)
            ],
        )
        con.commit()
    return len(SEED)


def list_routines(*, incluir_inativas: bool = False) -> list[dict]:
    where = "" if incluir_inativas else "WHERE ativo = 1"
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT {_ROUTINE_COLS} FROM routines {where} ORDER BY {_ROUTINE_ORDER}"
        ).fetchall()
    return [_routine(r) for r in rows]


def get_routine(id: int, *, incluir_inativas: bool = False) -> dict | None:
    where = "" if incluir_inativas else "AND ativo = 1"
    with closing(_connect()) as con:
        row = con.execute(
            f"SELECT {_ROUTINE_COLS} FROM routines WHERE id = ? {where}", (id,)
        ).fetchone()
    return _routine(row) if row is not None else None


def _unique_slug(con: sqlite3.Connection, base: str) -> str:
    """Sufixa -2, -3... na colisão. Compara contra TODAS as rotinas (inclusive as
    soft-deletadas): o slug de uma rotina apagada ainda é referenciado pelos checks
    antigos, então reciclá-lo misturaria dois históricos."""
    tomados = {
        r["slug"] for r in con.execute(
            "SELECT slug FROM routines WHERE slug = ? OR slug LIKE ? || '-%'",
            (base, base),
        )
    }
    if base not in tomados:
        return base
    n = 2
    while f"{base}-{n}" in tomados:
        n += 1
    return f"{base}-{n}"


def create_routine(
    nome: str,
    bloco: str,
    dias: str = "*",
    templates: str = "*",
    passos: list[str] | None = None,
    *,
    origem: str = "leo",
) -> dict:
    from .routines import slugify

    with closing(_connect()) as con:
        # slug único + ordem = max+1 do bloco: as duas leituras precisam ser
        # atômicas com o insert, senão dois creates simultâneos colidem.
        con.execute("BEGIN IMMEDIATE")
        slug = _unique_slug(con, slugify(nome))
        row = con.execute(
            "SELECT COALESCE(MAX(ordem), 0) FROM routines WHERE bloco = ?", (bloco,)
        ).fetchone()
        cur = con.execute(
            "INSERT INTO routines "
            "(slug, nome, bloco, dias, templates, passos, ordem, origem, ativo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                slug, nome, bloco, dias, templates,
                json.dumps(passos or []), int(row[0]) + 1, origem,
            ),
        )
        con.commit()
        new = con.execute(
            f"SELECT {_ROUTINE_COLS} FROM routines WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _routine(new)


def update_routine(id: int, **campos) -> dict | None:
    """Patch parcial. `slug` e `origem` NÃO são atualizáveis — o slug é a chave do
    histórico e a origem diz quem criou. Devolve None se a rotina não existe (ou já
    foi soft-deletada)."""
    permitidos = ("nome", "bloco", "dias", "templates", "passos", "ordem")
    sets, params = [], []
    for campo in permitidos:
        if campo not in campos or campos[campo] is None:
            continue
        valor = campos[campo]
        sets.append(f"{campo} = ?")
        params.append(json.dumps(valor) if campo == "passos" else valor)

    with closing(_connect()) as con:
        if sets:
            cur = con.execute(
                f"UPDATE routines SET {', '.join(sets)} WHERE id = ? AND ativo = 1",
                (*params, id),
            )
            con.commit()
            if cur.rowcount == 0:
                return None
        row = con.execute(
            f"SELECT {_ROUTINE_COLS} FROM routines WHERE id = ? AND ativo = 1", (id,)
        ).fetchone()
    return _routine(row) if row is not None else None


def delete_routine(id: int) -> bool:
    """Soft delete. A linha fica (o slug continua amarrando os checks antigos), some
    das listagens e do fechamento."""
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE routines SET ativo = 0 WHERE id = ? AND ativo = 1", (id,)
        )
        con.commit()
        return cur.rowcount == 1


def reorder_routines(pares: list[tuple[int, int]]) -> int:
    """Reordena em lote (drag-and-drop do app). Ignora ids inexistentes/inativos."""
    with closing(_connect()) as con:
        cur = con.executemany(
            "UPDATE routines SET ordem = ? WHERE id = ? AND ativo = 1",
            [(int(ordem), int(id)) for id, ordem in pares],
        )
        con.commit()
        return cur.rowcount


# --- sessions ---------------------------------------------------------------


def add_session(
    tipo,
    projeto,
    categoria,
    inicio,
    fim,
    duracao_s,
    paginas,
    livro,
    *,
    return_created=False,
    session_key=None,
) -> int | tuple[int, bool]:
    """Insere uma sessão e devolve seu id.

    `return_created=True` também devolve se esta chamada inseriu a linha. Isso
    permite ao endpoint evitar repetir telemetria após um retry deduplicado.
    """
    with closing(_connect()) as con:
        if session_key is not None:
            # Serializa select+insert entre escritores. Se uma resposta se perdeu,
            # o retry encontra exatamente a sessão originalmente registrada.
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT id FROM sessions WHERE session_key = ?",
                (session_key,),
            ).fetchone()
            if row is not None:
                con.commit()
                sid = int(row["id"])
                return (sid, False) if return_created else sid
            cur = con.execute(
                "INSERT INTO sessions "
                "(tipo, projeto, categoria, inicio, fim, duracao_s, paginas, "
                "livro, session_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tipo,
                    projeto,
                    categoria,
                    inicio,
                    fim,
                    duracao_s,
                    paginas,
                    livro,
                    session_key,
                ),
            )
        else:
            cur = con.execute(
                "INSERT INTO sessions "
                "(tipo, projeto, categoria, inicio, fim, duracao_s, paginas, livro) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tipo, projeto, categoria, inicio, fim, duracao_s, paginas, livro),
            )
        con.commit()
        sid = int(cur.lastrowid)
        return (sid, True) if return_created else sid


def get_session_inicio(session_id: int) -> float:
    """Recupera o início persistido para manter o caminho Raw estável em retries."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT inicio FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        raise LookupError("sessão não encontrada")
    return float(row["inicio"])


def list_sessions_since(ts: float) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM sessions WHERE inicio >= ? ORDER BY inicio",
            (ts,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- telemetry --------------------------------------------------------------


def log_event(evento: str, ref: str = "", meta: dict | None = None) -> None:
    """Registra um evento de telemetria. `meta` NUNCA carrega conteúdo de captura
    (lei 7) — apenas metadados sem PII (contadores, ids, classes de erro)."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO telemetry (ts, evento, ref, meta_json) VALUES (?, ?, ?, ?)",
            (time.time(), evento, ref, json.dumps(meta or {})),
        )
        con.commit()


def count_events_since(evento: str, ts: float) -> int:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT COUNT(DISTINCT ref) FROM telemetry "
            "WHERE evento = ? AND ts >= ?",
            (evento, ts),
        ).fetchone()
    return int(row[0])


# --- notif_log (dedupe por dia) ---------------------------------------------


def log_notif(evento: str, canal: str, entregue: bool) -> None:
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO notif_log (ts, data_local, evento, canal, entregue) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), date.today().isoformat(), evento, canal, int(entregue)),
        )
        con.commit()


def notif_sent_today(evento: str) -> bool:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT 1 FROM notif_log "
            "WHERE evento = ? AND data_local = ? AND entregue = 1 LIMIT 1",
            (evento, date.today().isoformat()),
        ).fetchone()
    return row is not None


# --- capture_queue (pending -> processing -> done | failed) ------------------


def enqueue_capture(
    text: str,
    profile: str | None,
    client_key: str | None = None,
) -> int:
    with closing(_connect()) as con:
        if client_key is not None:
            # Serializa select+insert entre escritores. Se uma resposta se perdeu,
            # o retry encontra e devolve exatamente o id originalmente enfileirado.
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT id FROM capture_queue WHERE client_key = ?",
                (client_key,),
            ).fetchone()
            if row is not None:
                con.commit()
                return int(row["id"])
            cur = con.execute(
                "INSERT INTO capture_queue (ts, text, profile, client_key) "
                "VALUES (?, ?, ?, ?)",
                (time.time(), text, profile, client_key),
            )
        else:
            cur = con.execute(
                "INSERT INTO capture_queue (ts, text, profile) VALUES (?, ?, ?)",
                (time.time(), text, profile),
            )
        con.commit()
        return int(cur.lastrowid)


def pending_captures(max_attempts: int = MAX_ATTEMPTS) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT {_CAPTURE_COLS} FROM capture_queue "
            "WHERE status = 'pending' AND attempts < ? ORDER BY id",
            (max_attempts,),
        ).fetchall()
    return [dict(r) for r in rows]


def claim_capture(id: int) -> bool:
    """Toma posse atômica de um item ainda pendente."""
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE capture_queue SET status = 'processing' "
            "WHERE id = ? AND status = 'pending'",
            (id,),
        )
        con.commit()
        return cur.rowcount == 1


def recover_processing() -> int:
    """Reapresenta itens órfãos deixados em processing por crash do worker."""
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE capture_queue SET status = 'pending' "
            "WHERE status = 'processing'"
        )
        con.commit()
        return cur.rowcount


def failed_captures() -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT {_CAPTURE_COLS} FROM capture_queue "
            "WHERE status = 'failed' ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def mark_capture(
    id,
    *,
    status=None,
    raw_path=None,
    clickup_task_id=None,
    error=None,
    bump_attempts=False,
) -> None:
    """Atualiza um item da fila. `error` é a classe/código do erro sanitizado pelo
    chamador — NUNCA o conteúdo capturado (lei 7), pois vai para `last_error`.

    Auto-failover: uma falha devolve o item de `processing` para `pending`; quando
    `attempts` chega a `MAX_ATTEMPTS`, ele sai da fila ativa como `failed`, mas
    permanece na tabela (lei 1: failed nunca é descartado, é reapresentado)."""
    with closing(_connect()) as con:
        if bump_attempts and status is None:
            row = con.execute(
                "SELECT attempts FROM capture_queue WHERE id = ?", (id,)
            ).fetchone()
            if row is not None:
                status = (
                    "failed"
                    if row["attempts"] + 1 >= MAX_ATTEMPTS
                    else "pending"
                )

        sets, params = [], []
        if bump_attempts:
            sets.append("attempts = attempts + 1")
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if raw_path is not None:
            sets.append("raw_path = ?")
            params.append(raw_path)
        if clickup_task_id is not None:
            sets.append("clickup_task_id = ?")
            params.append(clickup_task_id)
        if error is not None:
            sets.append("last_error = ?")
            params.append(error)
        elif status == "done":
            sets.append("last_error = NULL")
        if not sets:
            return
        con.execute(
            f"UPDATE capture_queue SET {', '.join(sets)} WHERE id = ?",
            (*params, id),
        )
        con.commit()

def retry_failed_captures() -> int:
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE capture_queue SET status = 'pending', attempts = 0 "
            "WHERE status = 'failed'"
        )
        con.commit()
        return cur.rowcount


# --- digest_runs ------------------------------------------------------------


def save_digest_run(data_local: str, body: str, count: int, delivered: bool) -> None:
    with closing(_connect()) as con:
        con.execute(
            "INSERT OR REPLACE INTO digest_runs "
            "(data_local, body, count, delivered, ts) VALUES (?, ?, ?, ?, ?)",
            (data_local, body, int(count), int(delivered), time.time()),
        )
        con.commit()


def get_digest_run(data_local: str) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM digest_runs WHERE data_local = ?", (data_local,)
        ).fetchone()
    return dict(row) if row is not None else None


# --- scheduler (hora marcada) -----------------------------------------------


def add_schedule(quando_ts: float, tipo: str, ref: str) -> int:
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT INTO scheduler (quando, tipo, ref) VALUES (?, ?, ?)",
            (quando_ts, tipo, ref),
        )
        con.commit()
        return int(cur.lastrowid)


def has_schedule_ref(fragment: str) -> bool:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT 1 FROM scheduler "
            "WHERE ref LIKE '%' || ? || '%' LIMIT 1",
            (fragment,),
        ).fetchone()
    return row is not None


def due_schedules(now_ts: float) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM scheduler WHERE disparado = 0 AND quando <= ? "
            "ORDER BY quando, id",
            (now_ts,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_schedule_fired(id: int) -> None:
    with closing(_connect()) as con:
        con.execute("UPDATE scheduler SET disparado = 1 WHERE id = ?", (id,))
        con.commit()


def pending_schedules() -> list[dict]:
    """Tudo que ainda não disparou (não só o vencido) — os follow-ups do Shutdown."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM scheduler WHERE disparado = 0 ORDER BY quando, id"
        ).fetchall()
    return [dict(r) for r in rows]


def schedules_between(inicio_ts: float, fim_ts: float) -> list[dict]:
    """Itens de hora marcada de uma janela [início, fim) — os `horarios` da abertura.
    Traz também os já disparados: é a AGENDA do dia, não uma fila de pendências."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM scheduler WHERE quando >= ? AND quando < ? "
            "ORDER BY quando, id",
            (inicio_ts, fim_ts),
        ).fetchall()
    return [dict(r) for r in rows]


# --- dia (A1a toque das 5h30 + A1b check-in das 8h20) -----------------------
# Uma linha por data. As duas escritas são UPSERT PARCIAL, não REPLACE cego: o toque
# não pode apagar o check-in e o check-in não pode apagar o toque (eles acontecem em
# horas diferentes do MESMO dia, e ordem nenhuma é garantida).


_DIA_COLS = "data, template, energia, clareza, prioridade_1, checkin_em"


def get_dia(data: str) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute(
            f"SELECT {_DIA_COLS} FROM dia WHERE data = ?", (data,)
        ).fetchone()
    return dict(row) if row is not None else None


def set_dia_template(data: str, template: str) -> dict:
    """O toque das 5h30: 'dia yoga' ou 'dia corrida'. Idempotente — reescrever o mesmo
    template (ou trocar de ideia) não perde o resto da linha."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO dia (data, template) VALUES (?, ?) "
            "ON CONFLICT(data) DO UPDATE SET template = excluded.template",
            (data, template),
        )
        con.commit()
    return get_dia(data)


def set_checkin(
    data: str,
    energia: str | None,
    clareza: str | None,
    prioridade_1: str | None,
) -> dict:
    """O check-in das 8h20. `checkin_em` é o carimbo de que ele ACONTECEU."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO dia (data, energia, clareza, prioridade_1, checkin_em) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(data) DO UPDATE SET "
            "energia = excluded.energia, clareza = excluded.clareza, "
            "prioridade_1 = excluded.prioridade_1, checkin_em = excluded.checkin_em",
            (data, energia, clareza, prioridade_1, time.time()),
        )
        con.commit()
    return get_dia(data)


# --- shutdown (A2, 19h) ------------------------------------------------------


def get_shutdown(data: str) -> dict | None:
    """`prioridades` volta como lista (no banco é JSON). São as prioridades de AMANHÃ —
    é isto que o GET /abertura do dia seguinte lê em `prioridades_de_ontem`."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT data, prioridades, feito_em FROM shutdown WHERE data = ?", (data,)
        ).fetchone()
    if row is None:
        return None
    r = dict(row)
    try:
        prioridades = json.loads(r.get("prioridades") or "[]")
    except (TypeError, ValueError):
        prioridades = []
    r["prioridades"] = prioridades if isinstance(prioridades, list) else []
    return r


def save_shutdown(data: str, prioridades: list[str]) -> dict:
    """Salva o plano de amanhã e marca o rito como feito. REPLACE: refazer o Shutdown no
    mesmo dia substitui o plano (o último é o que vale)."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT OR REPLACE INTO shutdown (data, prioridades, feito_em) "
            "VALUES (?, ?, ?)",
            (data, json.dumps(list(prioridades)), time.time()),
        )
        con.commit()
    return get_shutdown(data)

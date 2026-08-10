"""Persistência local do P1 (sqlite3 síncrono).

Único dono do schema e das conexões. `_connect()` é o helper interno único: toda
conexão nasce em WAL + busy_timeout (worker de captura e endpoints escrevem em
paralelo, então a concorrência é real). `init_db()` aplica o schema inteiro de
forma idempotente e é chamado no startup (main.lifespan).

Higiene (lei 7): `log_event.meta` e `capture_queue.last_error` NUNCA recebem o
conteúdo capturado — só classe/código de erro e metadados sem PII.
"""
import json
import logging
import sqlite3
import time
import unicodedata
from uuid import uuid4
from contextlib import closing
from datetime import date
from pathlib import Path

from . import tz
from .config import settings

logger = logging.getLogger(__name__)

# Teto de tentativas da fila de captura. `pending_captures` esconde quem passou
# do teto e `mark_capture(bump_attempts=True)` marca 'failed' ao atingi-lo.
MAX_ATTEMPTS = 5
CLAIM_STALE_SECONDS = 300

# Colunas do contrato de fila (Tasks 9/10/12). `status` fica de fora de propósito:
# em `pending_captures` é sempre 'pending', em `failed_captures` sempre 'failed'.
_CAPTURE_COLS = (
    "id, ts, text, profile, client_key, sensivel, attempts, raw_path, "
    "clickup_task_id, last_error"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
  token TEXT PRIMARY KEY, created REAL
);
CREATE TABLE IF NOT EXISTS push_receipts (
  ticket_id TEXT PRIMARY KEY, token TEXT NOT NULL, criado REAL NOT NULL
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
CREATE TABLE IF NOT EXISTS reduction_habits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  penalidade INTEGER NOT NULL DEFAULT 1,
  ativo INTEGER NOT NULL DEFAULT 1,
  criado REAL NOT NULL,
  atualizado REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reduction_occurrences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  habito_id INTEGER NOT NULL,
  data TEXT NOT NULL,
  registrada_em REAL NOT NULL,
  client_key TEXT UNIQUE,
  penalidade INTEGER NOT NULL,
  desfeita_em REAL
);
CREATE INDEX IF NOT EXISTS idx_reduction_occurrences_history
  ON reduction_occurrences(data, habito_id, registrada_em, id);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, projeto TEXT,
  categoria TEXT, inicio REAL NOT NULL, fim REAL NOT NULL,
  duracao_s INTEGER NOT NULL, paginas INTEGER, livro TEXT, session_key TEXT
);
CREATE TABLE IF NOT EXISTS reading_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_key TEXT NOT NULL UNIQUE,
  livro TEXT NOT NULL,
  pagina_inicial INTEGER,
  pagina_final INTEGER,
  inicio REAL NOT NULL,
  fim REAL,
  status TEXT NOT NULL DEFAULT 'pending',
  last_seq INTEGER NOT NULL DEFAULT 0,
  draft_md TEXT,
  vault_path TEXT,
  compiled_session_id INTEGER,
  source_digest TEXT,
  last_error TEXT,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reading_buffer (
  session_id INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  chunk_id TEXT NOT NULL,
  hook TEXT NOT NULL,
  texto TEXT NOT NULL,
  ts REAL NOT NULL,
  PRIMARY KEY (session_id, seq)
);
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'lendo',
  ciclo INTEGER NOT NULL DEFAULT 1,
  created REAL NOT NULL,
  updated REAL NOT NULL
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
  attempts INTEGER NOT NULL DEFAULT 0, raw_path TEXT, clickup_task_id TEXT, last_error TEXT,
  proxima_em REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS digest_runs (
  data_local TEXT PRIMARY KEY, body TEXT NOT NULL, count INTEGER NOT NULL,
  delivered INTEGER NOT NULL, ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
  semana TEXT PRIMARY KEY, feito_em REAL NOT NULL, vault_path TEXT
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
CREATE TABLE IF NOT EXISTS ics_cache (
  fonte TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  fetched REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS temas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  semana TEXT NOT NULL,
  texto TEXT NOT NULL,
  criado REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS objetivos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  rotina_slug TEXT,
  alvo_semana INTEGER,
  criado REAL NOT NULL,
  ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS objetivo_marcas (
  objetivo_id INTEGER NOT NULL,
  data TEXT NOT NULL,
  PRIMARY KEY (objetivo_id, data)
);
CREATE TABLE IF NOT EXISTS aprendizados (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  texto TEXT NOT NULL,
  sensivel INTEGER NOT NULL DEFAULT 0,
  origem_captura_id INTEGER UNIQUE,
  criado REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'novo',
  pratica_semana TEXT,
  pratica_em REAL
);
CREATE TABLE IF NOT EXISTS melhorias (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  texto TEXT NOT NULL,
  alvo TEXT,
  sensivel INTEGER NOT NULL DEFAULT 0,
  origem_captura_id INTEGER UNIQUE,
  criado REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'novo',
  escolhida_semana TEXT,
  escolhida_em REAL
);
CREATE TABLE IF NOT EXISTS anki_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER,
  frente TEXT NOT NULL,
  meaning TEXT NOT NULL DEFAULT '',
  example TEXT NOT NULL DEFAULT '',
  hook TEXT NOT NULL DEFAULT '',
  deck TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'sugerido',
  criado REAL NOT NULL,
  export_claimed REAL
);
CREATE TABLE IF NOT EXISTS anki_suggestion_runs (
  session_id INTEGER PRIMARY KEY,
  status TEXT NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL
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

        reading_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(reading_sessions)")
        }
        if "source_digest" not in reading_columns:
            con.execute("ALTER TABLE reading_sessions ADD COLUMN source_digest TEXT")

        buffer_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(reading_buffer)")
        }
        if "chunk_id" not in buffer_columns:
            con.execute("ALTER TABLE reading_buffer ADD COLUMN chunk_id TEXT")
        for row in con.execute(
            "SELECT session_id, seq FROM reading_buffer WHERE chunk_id IS NULL"
        ).fetchall():
            con.execute(
                "UPDATE reading_buffer SET chunk_id = ? "
                "WHERE session_id = ? AND seq = ?",
                (str(uuid4()), row["session_id"], row["seq"]),
            )
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_reading_buffer_chunk_id "
            "ON reading_buffer(chunk_id)"
        )

        # Recupera somente leases velhos. Outro worker pode chamar init_db enquanto
        # uma operação legítima está em voo; claims recentes continuam exclusivos.
        claim_cutoff = time.time() - CLAIM_STALE_SECONDS
        con.execute(
            "UPDATE reading_sessions SET status = 'pending' "
            "WHERE status = 'compiling' AND updated < ?",
            (claim_cutoff,),
        )
        con.execute(
            "DELETE FROM anki_suggestion_runs "
            "WHERE status = 'processing' AND updated < ?",
            (claim_cutoff,),
        )

        anki_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(anki_cards)")
        }
        if "export_claimed" not in anki_columns:
            con.execute("ALTER TABLE anki_cards ADD COLUMN export_claimed REAL")
        fila_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(capture_queue)")
        }
        if "proxima_em" not in fila_columns:
            con.execute(
                "ALTER TABLE capture_queue ADD COLUMN proxima_em REAL NOT NULL DEFAULT 0"
            )

        # Migração idempotente para bancos criados antes da estante. O índice vem
        # depois do ALTER porque num banco antigo as colunas que ele referencia
        # só passam a existir depois que o ALTER TABLE roda.
        reading_session_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(reading_sessions)")
        }
        for coluna, tipo in (
            ("book_id", "INTEGER"),
            ("book_ciclo", "INTEGER"),
            ("compiled_at", "REAL"),
            ("draft_fmt", "INTEGER"),
        ):
            if coluna not in reading_session_columns:
                con.execute(f"ALTER TABLE reading_sessions ADD COLUMN {coluna} {tipo}")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_reading_sessions_book "
            "ON reading_sessions(book_id, book_ciclo, compiled_at)"
        )

        con.execute(
            "UPDATE anki_cards SET status = 'aprovado', export_claimed = NULL "
            "WHERE status = 'exporting' "
            "AND (export_claimed IS NULL OR export_claimed < ?)",
            (claim_cutoff,),
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

        # A marca por captura é fail-closed: ausência em bancos antigos equivale a
        # falso, e o ALTER preserva todas as filas já existentes.
        if "sensivel" not in columns:
            con.execute(
                "ALTER TABLE capture_queue "
                "ADD COLUMN sensivel INTEGER NOT NULL DEFAULT 0"
            )
        # Área proposta na CLASSIFICAÇÃO, não na abertura da triagem. NULL é o
        # estado normal de item que entrou no Staging por fora da captura (criado
        # à mão no ClickUp, ou anterior a esta coluna) — a triagem mostra sem
        # sugestão e o Leo escolhe. Ver `tasks.triagem_pack`.
        if "area_proposta" not in columns:
            con.execute("ALTER TABLE capture_queue ADD COLUMN area_proposta TEXT")
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
        rows = con.execute(
            "SELECT token FROM devices ORDER BY created, token"
        ).fetchall()
    return [r[0] for r in rows]


def remove_devices(tokens: list[str]) -> int:
    """Remove somente tokens confirmados stale pelo ticket correspondente do Expo."""
    unicos = list(dict.fromkeys(token for token in tokens if token))
    if not unicos:
        return 0
    placeholders = ",".join("?" for _ in unicos)
    with closing(_connect()) as con:
        cur = con.execute(
            f"DELETE FROM devices WHERE token IN ({placeholders})",
            unicos,
        )
        con.commit()
        return cur.rowcount


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


# --- habitos a reduzir -------------------------------------------------------
# Definicoes usam soft-delete e ocorrencias usam soft-undo: o placar e o historico
# continuam recalculaveis sem um ledger mutavel nem destruicao de dados passados.

_REDUCTION_HABIT_COLS = "id, slug, nome, penalidade, criado, atualizado"


def list_reduction_habits(*, incluir_inativos: bool = False) -> list[dict]:
    where = "" if incluir_inativos else "WHERE ativo = 1"
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT {_REDUCTION_HABIT_COLS} FROM reduction_habits "
            f"{where} ORDER BY nome COLLATE NOCASE, id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_reduction_habit(
    id: int,
    *,
    incluir_inativos: bool = False,
) -> dict | None:
    active = "" if incluir_inativos else "AND ativo = 1"
    with closing(_connect()) as con:
        row = con.execute(
            f"SELECT {_REDUCTION_HABIT_COLS} FROM reduction_habits "
            f"WHERE id = ? {active}",
            (id,),
        ).fetchone()
    return dict(row) if row is not None else None


def _unique_reduction_slug(con: sqlite3.Connection, nome: str) -> str:
    from .routines import slugify

    base = slugify(nome)
    taken = {
        row["slug"]
        for row in con.execute(
            "SELECT slug FROM reduction_habits "
            "WHERE slug = ? OR slug LIKE ? || '-%'",
            (base, base),
        )
    }
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


def create_reduction_habit(nome: str, penalidade: int = 1) -> dict:
    now = time.time()
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        slug = _unique_reduction_slug(con, nome)
        cur = con.execute(
            "INSERT INTO reduction_habits "
            "(slug, nome, penalidade, criado, atualizado) VALUES (?, ?, ?, ?, ?)",
            (slug, nome, int(penalidade), now, now),
        )
        row = con.execute(
            f"SELECT {_REDUCTION_HABIT_COLS} FROM reduction_habits WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        con.commit()
    assert row is not None
    return dict(row)


def update_reduction_habit(id: int, **fields) -> dict | None:
    allowed = ("nome", "penalidade")
    sets: list[str] = []
    params: list = []
    for field in allowed:
        if field not in fields or fields[field] is None:
            continue
        sets.append(f"{field} = ?")
        params.append(fields[field])

    with closing(_connect()) as con:
        if sets:
            sets.append("atualizado = ?")
            params.append(time.time())
            cur = con.execute(
                f"UPDATE reduction_habits SET {', '.join(sets)} "
                "WHERE id = ? AND ativo = 1",
                (*params, id),
            )
            if cur.rowcount != 1:
                con.commit()
                return None
        row = con.execute(
            f"SELECT {_REDUCTION_HABIT_COLS} FROM reduction_habits "
            "WHERE id = ? AND ativo = 1",
            (id,),
        ).fetchone()
        con.commit()
    return dict(row) if row is not None else None


def delete_reduction_habit(id: int) -> bool:
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE reduction_habits SET ativo = 0, atualizado = ? "
            "WHERE id = ? AND ativo = 1",
            (time.time(), id),
        )
        con.commit()
        return cur.rowcount == 1


_REDUCTION_OCCURRENCE_SELECT = """
SELECT
  o.id, o.habito_id, o.data, o.registrada_em, o.client_key,
  o.penalidade, o.desfeita_em, h.slug, h.nome,
  CASE WHEN o.desfeita_em IS NULL AND o.id = (
    SELECT first_active.id
    FROM reduction_occurrences AS first_active
    WHERE first_active.habito_id = o.habito_id
      AND first_active.data = o.data
      AND first_active.desfeita_em IS NULL
    ORDER BY first_active.registrada_em, first_active.id
    LIMIT 1
  ) THEN 1 ELSE 0 END AS penalizavel
FROM reduction_occurrences AS o
JOIN reduction_habits AS h ON h.id = o.habito_id
"""


def _reduction_occurrence(row: sqlite3.Row) -> dict:
    payload = dict(row)
    payload["penalizavel"] = bool(payload["penalizavel"])
    payload["desfeita"] = payload["desfeita_em"] is not None
    return payload


def _get_reduction_occurrence(
    con: sqlite3.Connection,
    occurrence_id: int,
) -> dict | None:
    row = con.execute(
        _REDUCTION_OCCURRENCE_SELECT + " WHERE o.id = ?",
        (occurrence_id,),
    ).fetchone()
    return _reduction_occurrence(row) if row is not None else None


def record_reduction_occurrence(
    habit_id: int,
    data: str,
    *,
    client_key: str | None = None,
) -> tuple[str, dict | None]:
    """Registra um fato; retry por client_key devolve a mesma ocorrencia."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        if client_key is not None:
            existing = con.execute(
                "SELECT id, habito_id, data FROM reduction_occurrences "
                "WHERE client_key = ?",
                (client_key,),
            ).fetchone()
            if existing is not None:
                if existing["habito_id"] != habit_id or existing["data"] != data:
                    con.rollback()
                    raise ValueError("reduction_client_key_divergente")
                payload = _get_reduction_occurrence(con, existing["id"])
                con.commit()
                return "existing", payload

        habit = con.execute(
            "SELECT penalidade FROM reduction_habits WHERE id = ? AND ativo = 1",
            (habit_id,),
        ).fetchone()
        if habit is None:
            con.rollback()
            return "missing", None

        cur = con.execute(
            "INSERT INTO reduction_occurrences "
            "(habito_id, data, registrada_em, client_key, penalidade) "
            "VALUES (?, ?, ?, ?, ?)",
            (habit_id, data, time.time(), client_key, int(habit["penalidade"])),
        )
        payload = _get_reduction_occurrence(con, int(cur.lastrowid))
        con.commit()
    return "created", payload


def list_reduction_occurrences(
    *,
    desde: str | None = None,
    ate: str | None = None,
    habit_id: int | None = None,
    incluir_desfeitas: bool = True,
) -> list[dict]:
    where: list[str] = []
    params: list = []
    if desde is not None:
        where.append("o.data >= ?")
        params.append(desde)
    if ate is not None:
        where.append("o.data <= ?")
        params.append(ate)
    if habit_id is not None:
        where.append("o.habito_id = ?")
        params.append(habit_id)
    if not incluir_desfeitas:
        where.append("o.desfeita_em IS NULL")

    sql = _REDUCTION_OCCURRENCE_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.data DESC, o.registrada_em DESC, o.id DESC"
    with closing(_connect()) as con:
        rows = con.execute(sql, params).fetchall()
    return [_reduction_occurrence(row) for row in rows]


def undo_reduction_occurrence(occurrence_id: int) -> tuple[dict | None, bool]:
    """Soft-undo idempotente; preservar a linha mantem o historico auditavel."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT desfeita_em FROM reduction_occurrences WHERE id = ?",
            (occurrence_id,),
        ).fetchone()
        if row is None:
            con.rollback()
            return None, False
        changed = row["desfeita_em"] is None
        if changed:
            con.execute(
                "UPDATE reduction_occurrences SET desfeita_em = ? WHERE id = ?",
                (time.time(), occurrence_id),
            )
        payload = _get_reduction_occurrence(con, occurrence_id)
        con.commit()
    return payload, changed


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


def session_exists(session_id: int) -> bool:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT 1 FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return row is not None


def list_sessions_since(
    ts: float,
    until_ts: float | None = None,
) -> list[dict]:
    """Lista sessões numa janela semiaberta; sem limite preserva o contrato atual."""
    consulta = "SELECT * FROM sessions WHERE inicio >= ?"
    parametros: tuple = (ts,)
    if until_ts is not None:
        consulta += " AND inicio < ?"
        parametros += (until_ts,)
    consulta += " ORDER BY inicio"

    with closing(_connect()) as con:
        rows = con.execute(consulta, parametros).fetchall()
    return [dict(r) for r in rows]


# --- books (estante, fatia 1) ------------------------------------------------


def slug_livro(titulo: str) -> str:
    """Normaliza caixa, acento e espaço — e SÓ isso.

    Pontuação fica: descartá-la colapsaria "C", "C++" e "C#" numa obra só. O slug
    serve para não criar "Sapiens" e "sapiens " como duas obras, não para ser
    identidade semântica.
    """
    sem_acento = "".join(
        c
        for c in unicodedata.normalize("NFD", titulo)
        if unicodedata.category(c) != "Mn"
    )
    # Categoria "C*" cobre controle e formatação; vira espaço para o split colapsar.
    limpo = "".join(
        " " if unicodedata.category(c).startswith("C") else c for c in sem_acento
    )
    return " ".join(limpo.casefold().split())


def create_book(titulo: str) -> tuple[dict, bool]:
    """Cria ou reusa a obra de mesmo slug. Concorrência resolvida no banco."""
    slug = slug_livro(titulo)
    if not slug:
        raise ValueError("titulo_invalido")
    agora = time.time()
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "INSERT INTO books (titulo, slug, status, ciclo, created, updated) "
            "VALUES (?, ?, 'lendo', 1, ?, ?) ON CONFLICT(slug) DO NOTHING",
            (" ".join(titulo.split()), slug, agora, agora),
        )
        criado = cur.rowcount == 1
        row = con.execute("SELECT * FROM books WHERE slug = ?", (slug,)).fetchone()
        con.commit()
        return dict(row), criado


def get_book(book_id: int) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    return None if row is None else dict(row)


_ESTANTE_SQL = """
SELECT
  b.id, b.titulo, b.status, b.ciclo,
  (SELECT s.pagina_final FROM reading_sessions s
     WHERE s.book_id = b.id AND s.book_ciclo = b.ciclo
       AND s.status = 'compiled' AND s.pagina_final IS NOT NULL
     ORDER BY s.compiled_at DESC, s.id DESC LIMIT 1) AS pagina_atual,
  (SELECT MAX(s.compiled_at) FROM reading_sessions s
     WHERE s.book_id = b.id AND s.book_ciclo = b.ciclo
       AND s.status = 'compiled') AS ultima_sessao,
  (SELECT COUNT(*) FROM reading_sessions s
     WHERE s.book_id = b.id AND s.book_ciclo = b.ciclo
       AND s.status = 'compiled') AS sessoes_n
FROM books b
WHERE b.status = ?
ORDER BY ultima_sessao IS NULL, ultima_sessao DESC, b.id DESC
"""


def list_books(status: str = "lendo") -> list[dict]:
    """Estante: uma query só, com o progresso derivado das sessões do ciclo atual.

    `pagina_atual` ordena por `compiled_at` (relógio do servidor) e não por `fim`,
    que vem do cliente — celular atrasado apontaria a sessão errada como a última.
    `ultima_sessao IS NULL` primeiro no ORDER BY faz obra sem leitura cair no fim
    sem depender de NULLS LAST, que nem toda versão de SQLite tem.
    """
    with closing(_connect()) as con:
        rows = con.execute(_ESTANTE_SQL, (status,)).fetchall()
    return [dict(r) for r in rows]


def terminar_book(book_id: int) -> tuple[str, dict | None]:
    """Fecha o ciclo. Sem efeito externo: é um UPDATE condicional e acabou.

    A tarefa de resumão no ClickUp é a fatia 2. Enquanto ela não existe, não há
    nada a reconciliar, então não há claim, lease nem status 'terminando'.
    """
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if row is None:
            con.rollback()
            return "missing", None
        abertas = con.execute(
            "SELECT id FROM reading_sessions WHERE book_id = ? AND book_ciclo = ? "
            "AND status IN ('pending', 'compiling') ORDER BY id",
            (book_id, row["ciclo"]),
        ).fetchall()
        if abertas:
            con.rollback()
            return "sessao_aberta", {"sessions": [r["id"] for r in abertas]}
        cur = con.execute(
            "UPDATE books SET status = 'terminado', updated = ? "
            "WHERE id = ? AND status = 'lendo'",
            (time.time(), book_id),
        )
        if cur.rowcount != 1:
            con.rollback()
            return "ja_terminado", None
        atualizado = con.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        con.commit()
        return "terminado", dict(atualizado)


def reabrir_book(book_id: int) -> tuple[str, dict | None]:
    """Releitura abre um ciclo NOVO: a página recomeça e o histórico fica intacto."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT id FROM books WHERE id = ?", (book_id,)).fetchone()
        if row is None:
            con.rollback()
            return "missing", None
        cur = con.execute(
            "UPDATE books SET status = 'lendo', ciclo = ciclo + 1, updated = ? "
            "WHERE id = ? AND status = 'terminado'",
            (time.time(), book_id),
        )
        if cur.rowcount != 1:
            con.rollback()
            return "ja_lendo", None
        atualizado = con.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        con.commit()
        return "reaberto", dict(atualizado)


# --- reading_sessions / reading_buffer (B7) ---------------------------------


def _reading_payload(con: sqlite3.Connection, row: sqlite3.Row) -> dict:
    chunks = con.execute(
        "SELECT seq, chunk_id, hook, texto, ts FROM reading_buffer "
        "WHERE session_id = ? ORDER BY seq",
        (row["id"],),
    ).fetchall()
    payload = dict(row)
    payload["buffer"] = [dict(chunk) for chunk in chunks]
    payload["texto"] = "\n".join(chunk["texto"] for chunk in chunks)
    return payload


class BookIndisponivel(Exception):
    """A obra existe mas não aceita sessão nova (status != 'lendo').

    Separada de ValueError porque o HTTP é outro: 409 (conflito de estado) e não
    422 (referência inválida).
    """


def create_reading_session(
    client_key: str,
    livro: str,
    pagina_inicial: int | None = None,
    inicio: float | None = None,
    book_id: int | None = None,
) -> tuple[dict, bool]:
    """Cria uma sessão retomável; retry da mesma client_key devolve a original."""
    agora = time.time()
    inicio_real = agora if inicio is None else float(inicio)
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE client_key = ?",
            (client_key,),
        ).fetchone()
        if row is not None:
            con.commit()
            return _reading_payload(con, row), False

        book_ciclo = None
        if book_id is not None:
            book = con.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if book is None:
                con.rollback()
                raise ValueError("book_nao_encontrado")
            if book["status"] != "lendo":
                con.rollback()
                raise BookIndisponivel("book_nao_aceita_sessao")
            # O ciclo é COPIADO, nunca inferido por tempo: `inicio` vem do cliente.
            book_ciclo = book["ciclo"]
            livro = book["titulo"]

        cur = con.execute(
            "INSERT INTO reading_sessions "
            "(client_key, livro, pagina_inicial, inicio, created, updated, "
            "book_id, book_ciclo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                client_key,
                livro,
                pagina_inicial,
                inicio_real,
                agora,
                agora,
                book_id,
                book_ciclo,
            ),
        )
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        con.commit()
        return _reading_payload(con, row), True


def get_reading_session(session_id: int) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return _reading_payload(con, row) if row is not None else None


def get_reading_session_by_compiled_id(compiled_session_id: int) -> dict | None:
    """Sentido inverso de `compiled_session_id`: de `sessions.id` para a
    `reading_sessions` que o gerou.

    `sessions.id` e `reading_sessions.id` são sequências AUTOINCREMENT
    independentes — mesmo valor numérico não implica mesma linha. Cada
    `reading_sessions` só grava seu próprio `compiled_session_id` (via
    `session_key=f"reading:{id}"`, único), então no máximo uma linha aqui
    corresponde a um dado `compiled_session_id`.
    """
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE compiled_session_id = ?",
            (compiled_session_id,),
        ).fetchone()
        return _reading_payload(con, row) if row is not None else None


def list_pending_reading_sessions() -> list[dict]:
    """Inclui uma compilação em voo: a fila nunca some enquanto não finalizar."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM reading_sessions "
            "WHERE status IN ('pending', 'compiling') "
            "ORDER BY updated ASC, id ASC"
        ).fetchall()
        return [_reading_payload(con, row) for row in rows]


def append_reading_buffer(
    session_id: int,
    seq: int,
    hook: str,
    texto: str,
    ts: float | None = None,
) -> tuple[dict, bool]:
    """Acrescenta o próximo chunk; retry igual é no-op, colisão/gap falha fechado."""
    agora = time.time()
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        session = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session is None:
            con.commit()
            raise LookupError("reading_session_nao_encontrada")
        if session["status"] != "pending":
            con.commit()
            raise ValueError("reading_session_nao_editavel")
        if session["draft_md"] is not None:
            con.commit()
            raise ValueError("reading_draft_ja_gerado")

        existing = con.execute(
            "SELECT seq, chunk_id, hook, texto, ts FROM reading_buffer "
            "WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        ).fetchone()
        if existing is not None:
            con.commit()
            if existing["hook"] == hook and existing["texto"] == texto:
                return dict(existing), False
            raise ValueError("reading_seq_conflitante")

        esperado = int(session["last_seq"]) + 1
        if seq != esperado:
            con.commit()
            raise ValueError(f"reading_seq_esperado_{esperado}")

        chunk_ts = agora if ts is None else float(ts)
        con.execute(
            "INSERT INTO reading_buffer "
            "(session_id, seq, chunk_id, hook, texto, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, seq, str(uuid4()), hook, texto, chunk_ts),
        )
        con.execute(
            "UPDATE reading_sessions SET last_seq = ?, updated = ?, last_error = NULL "
            "WHERE id = ?",
            (seq, agora, session_id),
        )
        row = con.execute(
            "SELECT seq, chunk_id, hook, texto, ts FROM reading_buffer "
            "WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        ).fetchone()
        con.commit()
        return dict(row), True


def update_last_reading_buffer(
    session_id: int,
    seq: int,
    *,
    expected_chunk_id: str,
    hook: str | None = None,
    texto: str | None = None,
) -> tuple[dict, bool]:
    """Corrige somente a cauda editavel; retry com o mesmo conteudo e no-op."""
    if hook is None and texto is None:
        raise ValueError("reading_patch_vazio")

    agora = time.time()
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        session = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session is None:
            con.rollback()
            raise LookupError("reading_session_nao_encontrada")
        if session["status"] != "pending":
            con.rollback()
            raise ValueError("reading_session_nao_editavel")
        if session["draft_md"] is not None:
            con.rollback()
            raise ValueError("reading_draft_ja_gerado")

        last_seq = int(session["last_seq"])
        if seq != last_seq:
            con.rollback()
            if seq > last_seq:
                raise LookupError("reading_item_nao_encontrado")
            raise ValueError("reading_apenas_ultimo_item_editavel")

        current = con.execute(
            "SELECT seq, chunk_id, hook, texto, ts FROM reading_buffer "
            "WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        ).fetchone()
        if current is None:
            con.rollback()
            raise ValueError("reading_buffer_inconsistente")
        if current["chunk_id"] != expected_chunk_id:
            con.rollback()
            raise ValueError("reading_item_foi_substituido")

        next_hook = current["hook"] if hook is None else hook
        next_text = current["texto"] if texto is None else texto
        changed = current["hook"] != next_hook or current["texto"] != next_text
        if changed:
            con.execute(
                "UPDATE reading_buffer SET hook = ?, texto = ? "
                "WHERE session_id = ? AND seq = ?",
                (next_hook, next_text, session_id, seq),
            )
            con.execute(
                "UPDATE reading_sessions SET updated = ?, last_error = NULL "
                "WHERE id = ?",
                (agora, session_id),
            )

        row = con.execute(
            "SELECT seq, chunk_id, hook, texto, ts FROM reading_buffer "
            "WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        ).fetchone()
        con.commit()
        return dict(row), changed


def delete_last_reading_buffer(
    session_id: int,
    seq: int,
    *,
    expected_chunk_id: str,
) -> tuple[dict, bool]:
    """Remove somente a cauda e reduz last_seq atomicamente; retry ausente e no-op."""
    agora = time.time()
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        session = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if session is None:
            con.rollback()
            raise LookupError("reading_session_nao_encontrada")
        if session["status"] != "pending":
            con.rollback()
            raise ValueError("reading_session_nao_editavel")
        if session["draft_md"] is not None:
            con.rollback()
            raise ValueError("reading_draft_ja_gerado")

        last_seq = int(session["last_seq"])
        if seq < last_seq:
            con.rollback()
            raise ValueError("reading_apenas_ultimo_item_editavel")
        if seq > last_seq:
            if seq != last_seq + 1:
                con.rollback()
                raise LookupError("reading_item_nao_encontrado")
            payload = _reading_payload(con, session)
            con.commit()
            return payload, False

        current = con.execute(
            "SELECT chunk_id FROM reading_buffer WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        ).fetchone()
        if current is None:
            con.rollback()
            raise ValueError("reading_buffer_inconsistente")
        if current["chunk_id"] != expected_chunk_id:
            con.rollback()
            raise ValueError("reading_item_foi_substituido")

        con.execute(
            "DELETE FROM reading_buffer WHERE session_id = ? AND seq = ?",
            (session_id, seq),
        )
        next_seq = int(
            con.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM reading_buffer WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
        )
        con.execute(
            "UPDATE reading_sessions SET last_seq = ?, updated = ?, last_error = NULL "
            "WHERE id = ?",
            (next_seq, agora, session_id),
        )
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        payload = _reading_payload(con, row)
        con.commit()
        return payload, True


def claim_reading_compile(session_id: int) -> tuple[str, dict | None]:
    """Serializa compile; o draft salvo sobrevive a falha posterior do vault."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            con.commit()
            return "missing", None
        if (
            row["status"] == "compiling"
            and float(row["updated"]) < time.time() - CLAIM_STALE_SECONDS
        ):
            con.execute(
                "UPDATE reading_sessions SET status = 'pending' WHERE id = ?",
                (session_id,),
            )
            row = con.execute(
                "SELECT * FROM reading_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row["status"] in {"compiled", "discarded", "compiling"}:
            state = str(row["status"])
            con.commit()
            return state, _reading_payload(con, row)
        if int(row["last_seq"]) == 0:
            con.commit()
            return "empty", _reading_payload(con, row)

        con.execute(
            "UPDATE reading_sessions SET status = 'compiling', updated = ? WHERE id = ?",
            (time.time(), session_id),
        )
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        con.commit()
        return "claimed", _reading_payload(con, row)


def stage_reading_draft(
    session_id: int, draft_md: str, source_digest: str, draft_fmt: int
) -> dict:
    """Guarda o preview e devolve a sessão a 'pending' (staged): fora do lock transitório
    de 'compiling', com o buffer congelado por draft_md não-nulo até aprovar/rejeitar."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "UPDATE reading_sessions SET draft_md = ?, source_digest = ?, "
            "draft_fmt = ?, status = 'pending', updated = ?, last_error = NULL "
            "WHERE id = ? AND status = 'compiling'",
            (draft_md, source_digest, draft_fmt, time.time(), session_id),
        )
        if cur.rowcount != 1:
            con.rollback()
            raise ValueError("reading_compile_sem_claim")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        con.commit()
        return _reading_payload(con, row)


def release_reading_compile(session_id: int, error: str) -> None:
    """Só persiste código/classe sanitizada; conteúdo nunca entra em last_error."""
    with closing(_connect()) as con:
        con.execute(
            "UPDATE reading_sessions SET status = 'pending', last_error = ?, updated = ? "
            "WHERE id = ? AND status = 'compiling'",
            (error, time.time(), session_id),
        )
        con.commit()


def finish_reading_compile(
    session_id: int,
    *,
    vault_path: str,
    compiled_session_id: int,
    pagina_final: int | None,
    fim: float,
    source_digest: str,
) -> dict:
    with closing(_connect()) as con:
        agora = time.time()
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "UPDATE reading_sessions SET status = 'compiled', vault_path = ?, "
            "compiled_session_id = ?, pagina_final = COALESCE(?, pagina_final), "
            "fim = ?, source_digest = ?, last_error = NULL, updated = ?, "
            "compiled_at = ? "
            "WHERE id = ? AND status = 'compiling'",
            (
                vault_path,
                compiled_session_id,
                pagina_final,
                fim,
                source_digest,
                agora,
                agora,
                session_id,
            ),
        )
        if cur.rowcount != 1:
            con.rollback()
            raise ValueError("reading_compile_sem_claim")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        con.commit()
        return _reading_payload(con, row)


def purge_reading_content(session_id: int) -> dict:
    """Após vault+Anki, mantém só metadados operacionais; conteúdo já é canônico."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ? AND status = 'compiled'",
            (session_id,),
        ).fetchone()
        if row is None:
            con.rollback()
            raise ValueError("reading_session_nao_compilada")
        con.execute(
            "DELETE FROM reading_buffer WHERE session_id = ?",
            (session_id,),
        )
        con.execute(
            "UPDATE reading_sessions SET draft_md = NULL, updated = ? WHERE id = ?",
            (time.time(), session_id),
        )
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        con.commit()
        return _reading_payload(con, row)


def discard_reading_session(session_id: int) -> tuple[str, dict | None]:
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            con.commit()
            return "missing", None
        if row["status"] == "discarded":
            con.commit()
            return "discarded", _reading_payload(con, row)
        if row["status"] != "pending":
            state = str(row["status"])
            con.commit()
            return state, _reading_payload(con, row)

        con.execute(
            "UPDATE reading_sessions SET status = 'discarded', updated = ?, "
            "last_error = NULL, draft_md = NULL WHERE id = ?",
            (time.time(), session_id),
        )
        con.execute(
            "DELETE FROM reading_buffer WHERE session_id = ?",
            (session_id,),
        )
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        con.commit()
        return "discarded", _reading_payload(con, row)


def reject_reading_draft(session_id: int) -> tuple[str, dict | None]:
    """Rejeita o preview staged: limpa draft_md e devolve o buffer à edição, SEM
    tocar nos chunks. Estados terminais/'compiling' sobem pro endpoint mapear.
    Idempotente: pending já sem draft é no-op."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            con.commit()
            return "missing", None
        if row["status"] != "pending":
            state = str(row["status"])
            con.commit()
            return state, _reading_payload(con, row)
        if row["draft_md"] is None:
            con.commit()
            return "pending", _reading_payload(con, row)

        con.execute(
            "UPDATE reading_sessions SET draft_md = NULL, source_digest = NULL, "
            "last_error = NULL, updated = ? WHERE id = ?",
            (time.time(), session_id),
        )
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        con.commit()
        return "pending", _reading_payload(con, row)


# --- telemetry --------------------------------------------------------------


def dias_desde_ultima_interacao() -> int:
    """Dias desde o último evento de telemetria — a assinatura de que o Leo esteve
    aqui. 0 quando nunca houve evento: primeiro uso NÃO é retorno (seria dar
    "bem-vindo de volta" na estreia)."""
    with closing(_connect()) as con:
        row = con.execute("SELECT MAX(ts) FROM telemetry").fetchone()
    ultimo = row[0] if row else None
    if not ultimo:
        return 0
    return max(0, int((time.time() - float(ultimo)) // 86400))


def record_review(semana: str, vault_path: str | None = None) -> None:
    """Marca que o review daquela semana aconteceu. Idempotente: aprovar 2x é o
    mesmo review, não dois."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO reviews (semana, feito_em, vault_path) VALUES (?, ?, ?) "
            "ON CONFLICT(semana) DO UPDATE SET feito_em = excluded.feito_em, "
            "vault_path = COALESCE(excluded.vault_path, reviews.vault_path)",
            (semana, time.time(), vault_path),
        )
        con.commit()


def review_feito(semana: str) -> bool:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT 1 FROM reviews WHERE semana = ?", (semana,)
        ).fetchone()
    return row is not None


def semanas_sem_review(desde: list[str]) -> list[str]:
    """Das semanas passadas informadas, quais ficaram sem review. É o que torna
    'review pulado 2x → Mentor' uma pergunta respondível."""
    if not desde:
        return []
    marcas = ",".join("?" for _ in desde)
    with closing(_connect()) as con:
        feitas = {
            row[0]
            for row in con.execute(
                f"SELECT semana FROM reviews WHERE semana IN ({marcas})", desde
            )
        }
    return [semana for semana in desde if semana not in feitas]


def registrar_tickets(pares: list[tuple[str, str]]) -> None:
    """Guarda (ticket, token) para conferir o recibo depois. O ticket só diz que a
    Expo ACEITOU a mensagem; quem diz se chegou é o recibo, minutos depois."""
    if not pares:
        return
    agora = time.time()
    with closing(_connect()) as con:
        con.executemany(
            "INSERT OR REPLACE INTO push_receipts (ticket_id, token, criado) "
            "VALUES (?, ?, ?)",
            [(tid, token, agora) for tid, token in pares],
        )
        con.commit()


def tickets_a_conferir(idade_minima_s: float = 900) -> list[dict]:
    """Só os maduros: a Expo leva minutos para publicar o recibo, e perguntar cedo
    demais devolve 'not ready' e vira ruído."""
    corte = time.time() - idade_minima_s
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT ticket_id, token, criado FROM push_receipts WHERE criado <= ? "
            "ORDER BY criado",
            (corte,),
        ).fetchall()
    return [dict(r) for r in rows]


def descartar_tickets(ids: list[str]) -> None:
    if not ids:
        return
    marcas = ",".join("?" for _ in ids)
    with closing(_connect()) as con:
        con.execute(f"DELETE FROM push_receipts WHERE ticket_id IN ({marcas})", ids)
        con.commit()


def log_event(evento: str, ref: str = "", meta: dict | None = None) -> None:
    """Registra um evento de telemetria. `meta` NUNCA carrega conteúdo de captura
    (lei 7) — apenas metadados sem PII (contadores, ids, classes de erro)."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO telemetry (ts, evento, ref, meta_json) VALUES (?, ?, ?, ?)",
            (time.time(), evento, ref, json.dumps(meta or {})),
        )
        con.commit()


def count_events_since(
    evento: str,
    ts: float,
    until_ts: float | None = None,
) -> int:
    """Conta referências distintas dentro de uma janela semiaberta opcional.

    O limite exclusivo permite fechar meses civis sem mudar o comportamento dos
    chamadores existentes, que continuam omitindo ``until_ts``.
    """
    consulta = (
        "SELECT COUNT(DISTINCT ref) FROM telemetry "
        "WHERE evento = ? AND ts >= ?"
    )
    parametros: tuple = (evento, ts)
    if until_ts is not None:
        consulta += " AND ts < ?"
        parametros += (until_ts,)

    with closing(_connect()) as con:
        row = con.execute(consulta, parametros).fetchone()
    return int(row[0])


def distinct_events(eventos: list[str]) -> list[dict]:
    """{evento, ref, ts} de cada par (evento, ref) DISTINTO, com o ts do PRIMEIRO
    registro do par.

    Existe para `pontos.py` derivar ganho do log de telemetria sem ledger. Duas
    escolhas que são contrato, não detalhe:

    * **Distinto por (evento, ref)**, não por linha. O log é append-only e o mesmo
      fato pode entrar duas vezes — retry de rede, ou uma tarefa reaberta e
      concluída de novo. Pontuar por linha pagaria duas vezes pelo mesmo ato.
    * **MIN(ts)**, não MAX. É quando o fato aconteceu; um reprocessamento tardio
      não pode mudar a semana em que ele conta e reescrever um placar já fechado.

    `ref` vazio é descartado: sem chave não há como deduplicar, e evento sem ref
    nunca é um ato pontuável (é contador agregado, tipo `push_device_expirado`).
    """
    if not eventos:
        return []
    marcas = ",".join("?" for _ in eventos)
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT evento, ref, MIN(ts) AS ts FROM telemetry "
            f"WHERE evento IN ({marcas}) AND ref <> '' "
            "GROUP BY evento, ref",
            list(eventos),
        ).fetchall()
    return [dict(r) for r in rows]


# --- notif_log (dedupe por dia) ---------------------------------------------


def log_notif(evento: str, canal: str, entregue: bool) -> None:
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO notif_log (ts, data_local, evento, canal, entregue) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), tz.hoje_local().isoformat(), evento, canal, int(entregue)),
        )
        con.commit()


def notif_sent_today(evento: str) -> bool:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT 1 FROM notif_log "
            "WHERE evento = ? AND data_local = ? AND entregue = 1 LIMIT 1",
            (evento, tz.hoje_local().isoformat()),
        ).fetchone()
    return row is not None


# --- capture_queue (pending -> processing -> done | failed) ------------------


def areas_propostas_por_task() -> dict[str, str]:
    """{clickup_task_id: area_proposta} das capturas que já foram classificadas.

    A triagem lê daqui em vez de perguntar ao Hermes: a proposta foi decidida uma
    vez, quando a captura foi processada. Item sem entrada aqui — criado à mão no
    ClickUp, ou anterior à coluna — simplesmente não tem sugestão, e a tela deixa
    o Leo escolher.
    """
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT clickup_task_id, area_proposta FROM capture_queue "
            "WHERE clickup_task_id IS NOT NULL AND area_proposta IS NOT NULL"
        ).fetchall()
    return {str(r["clickup_task_id"]): str(r["area_proposta"]) for r in rows}


def enqueue_capture(
    text: str,
    profile: str | None,
    client_key: str | None = None,
    sensivel: bool = False,
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
                "INSERT INTO capture_queue "
                "(ts, text, profile, client_key, sensivel) "
                "VALUES (?, ?, ?, ?, ?)",
                (time.time(), text, profile, client_key, int(sensivel)),
            )
        else:
            cur = con.execute(
                "INSERT INTO capture_queue "
                "(ts, text, profile, sensivel) VALUES (?, ?, ?, ?)",
                (time.time(), text, profile, int(sensivel)),
            )
        con.commit()
        return int(cur.lastrowid)


def pending_captures(max_attempts: int = MAX_ATTEMPTS) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT {_CAPTURE_COLS} FROM capture_queue "
            "WHERE status = 'pending' AND attempts < ? AND proxima_em <= ? "
            "ORDER BY id",
            (max_attempts, time.time()),
        ).fetchall()
    return [dict(r) for r in rows]


def proxima_tentativa_em(id: int) -> float:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT proxima_em FROM capture_queue WHERE id = ?", (id,)
        ).fetchone()
    return float(row["proxima_em"]) if row else 0.0


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


def _attempts_atual(con, id) -> int:
    row = con.execute("SELECT attempts FROM capture_queue WHERE id = ?", (id,)).fetchone()
    return int(row["attempts"]) if row else 0


def _espera_do_retry(tentativa: int) -> float:
    """30s, 2min, 4min30, 8min… (tentativa² × 30). Cobre um blip de rede sem gastar o
    orçamento, e dá tempo do Hermes voltar antes da última tentativa."""
    return (tentativa ** 2) * 30


def mark_capture(
    id,
    *,
    status=None,
    raw_path=None,
    clickup_task_id=None,
    error=None,
    bump_attempts=False,
    sensivel: bool | None = None,
    area_proposta: str | None = None,
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
            # Backoff: sem ele, MAX_ATTEMPTS=5 × worker de 5s queimava as 5 tentativas
            # em 25 segundos. Uma instabilidade curta do Hermes bastava para mandar a
            # captura pra `failed`, de onde ela só voltava com restart do BFF.
            sets.append("proxima_em = ?")
            params.append(time.time() + _espera_do_retry(_attempts_atual(con, id) + 1))
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if raw_path is not None:
            sets.append("raw_path = ?")
            params.append(raw_path)
        if clickup_task_id is not None:
            sets.append("clickup_task_id = ?")
            params.append(clickup_task_id)
        if sensivel is not None:
            sets.append("sensivel = ?")
            params.append(int(sensivel))
        if area_proposta is not None:
            sets.append("area_proposta = ?")
            params.append(area_proposta)
        if error is not None:
            sets.append("last_error = ?")
            params.append(error)
        elif status == "done":
            sets.append("last_error = NULL")
        if status == "done":
            # O Raw já é canônico. A fila transitória retém ids/checkpoints, não o
            # conteúdo privado depois que todas as etapas concluíram.
            sets.append("text = ''")
        if not sets:
            return
        con.execute(
            f"UPDATE capture_queue SET {', '.join(sets)} WHERE id = ?",
            (*params, id),
        )
        con.commit()

def reapresentar_failed(idade_minima_s: float = 3600) -> int:
    """Devolve à fila as capturas que falharam há tempo suficiente.

    `retry_failed_captures` só era chamado no boot (main.py), então sem reiniciar o
    BFF um item em `failed` ficava invisível para sempre — a lei 1 respeitada na
    letra (o registro fica) e violada no espírito. Roda periodicamente no worker.
    """
    corte = time.time() - idade_minima_s
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE capture_queue SET status = 'pending', attempts = 0, proxima_em = 0 "
            "WHERE status = 'failed' AND proxima_em <= ?",
            (corte,),
        )
        con.commit()
        return cur.rowcount


def retry_failed_captures() -> int:
    with closing(_connect()) as con:
        cur = con.execute(
            # `proxima_em` TAMBÉM zera: reapresentar sem limpar a espera devolvia o
            # item a `pending` e ele seguia invisível para `pending_captures`.
            "UPDATE capture_queue SET status = 'pending', attempts = 0, proxima_em = 0 "
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
    template não perde o resto da linha. Ao trocar de ideia, checks exclusivos do
    template anterior deixam de valer; checks universais permanecem."""
    with closing(_connect()) as con:
        anterior = con.execute(
            "SELECT template FROM dia WHERE data = ?",
            (data,),
        ).fetchone()
        con.execute(
            "INSERT INTO dia (data, template) VALUES (?, ?) "
            "ON CONFLICT(data) DO UPDATE SET template = excluded.template",
            (data, template),
        )
        if anterior is not None and anterior["template"] != template:
            con.execute(
                "DELETE FROM routine_checks WHERE data = ? AND rotina IN ("
                "SELECT slug FROM routines WHERE templates <> '*' "
                "AND instr(',' || templates || ',', ',' || ? || ',') = 0"
                ")",
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


# Cache ICS -----------------------------------------------------------------


def set_ics_cache(fonte: str, payload: str) -> None:
    """Guarda a última leitura válida sem registrar a URL secreta, conforme a lei 7."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT OR REPLACE INTO ics_cache (fonte, payload, fetched) "
            "VALUES (?, ?, ?)",
            (fonte, payload, time.time()),
        )
        con.commit()


def get_ics_cache(fonte: str) -> dict | None:
    """Retorna o payload e sua idade; a decisão de aceitar cache velho é do cliente."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT payload, fetched FROM ics_cache WHERE fonte = ?",
            (fonte,),
        ).fetchone()
    return dict(row) if row else None


# Temas da semana -----------------------------------------------------------


def add_tema(semana: str, texto: str) -> dict:
    """Registra um tema factual para aparecer todos os dias da semana, conforme a lei 4."""
    criado = time.time()
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT INTO temas (semana, texto, criado) VALUES (?, ?, ?)",
            (semana, texto, criado),
        )
        con.commit()
        tema_id = int(cur.lastrowid)
    return {
        "id": tema_id,
        "semana": semana,
        "texto": texto,
        "criado": criado,
    }


def list_temas(semana: str) -> list[dict]:
    """Lista os temas na ordem em que foram registrados."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM temas WHERE semana = ? ORDER BY criado, id",
            (semana,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_tema(id: int) -> bool:
    """Remove pelo identificador e informa factualmente se algo existia."""
    with closing(_connect()) as con:
        cur = con.execute("DELETE FROM temas WHERE id = ?", (id,))
        con.commit()
        return cur.rowcount > 0


# --- objetivos acumulativos --------------------------------------------------


def create_objetivo(
    nome: str,
    rotina_slug: str | None = None,
    alvo_semana: int | None = None,
) -> dict:
    """Cria um objetivo preservando desde o início sua fonte de progresso."""
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT INTO objetivos "
            "(nome, rotina_slug, alvo_semana, criado, ativo) "
            "VALUES (?, ?, ?, ?, 1)",
            (nome, rotina_slug, alvo_semana, time.time()),
        )
        con.commit()
        objetivo_id = int(cur.lastrowid)
    return get_objetivo(objetivo_id)


def list_objetivos(*, incluir_inativos: bool = False) -> list[dict]:
    """Lista ativos por padrão; inativos continuam disponíveis para histórico."""
    consulta = "SELECT * FROM objetivos"
    if not incluir_inativos:
        consulta += " WHERE ativo = 1"
    consulta += " ORDER BY id"

    with closing(_connect()) as con:
        rows = con.execute(consulta).fetchall()
    return [dict(row) for row in rows]


def get_objetivo(id: int) -> dict | None:
    """Obtém inclusive um objetivo inativo, necessário para consultar sua história."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM objetivos WHERE id = ?",
            (id,),
        ).fetchone()
    return dict(row) if row else None


def update_objetivo(id: int, **campos) -> dict | None:
    """Atualiza somente nome e alvo; a fonte não muda no meio do histórico."""
    permitidos = ("nome", "alvo_semana")
    invalidos = set(campos) - set(permitidos)
    if invalidos:
        raise ValueError(
            "campos não atualizáveis: " + ", ".join(sorted(invalidos)),
        )

    alteracoes = {
        campo: campos[campo]
        for campo in permitidos
        if campo in campos
    }
    if not alteracoes:
        atual = get_objetivo(id)
        return atual if atual and atual["ativo"] else None

    atribuicoes = ", ".join(f"{campo} = ?" for campo in alteracoes)
    parametros = (*alteracoes.values(), id)

    with closing(_connect()) as con:
        cur = con.execute(
            f"UPDATE objetivos SET {atribuicoes} "
            "WHERE id = ? AND ativo = 1",
            parametros,
        )
        con.commit()

    return get_objetivo(id) if cur.rowcount > 0 else None


def delete_objetivo(id: int) -> bool:
    """Desativa sem apagar as marcações, que permanecem como história factual."""
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE objetivos SET ativo = 0 "
            "WHERE id = ? AND ativo = 1",
            (id,),
        )
        con.commit()
        return cur.rowcount > 0


def marcar_objetivo(id: int, data: str) -> bool:
    """Marca uma data uma única vez e informa se uma linha nova foi inserida."""
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO objetivo_marcas (objetivo_id, data) "
            "SELECT ?, ? WHERE EXISTS ("
            "SELECT 1 FROM objetivos WHERE id = ? AND ativo = 1"
            ")",
            (id, data, id),
        )
        con.commit()
        return cur.rowcount > 0


def desmarcar_objetivo(id: int, data: str) -> bool:
    """Remove uma marca específica e informa se ela existia."""
    with closing(_connect()) as con:
        cur = con.execute(
            "DELETE FROM objetivo_marcas "
            "WHERE objetivo_id = ? AND data = ?",
            (id, data),
        )
        con.commit()
        return cur.rowcount > 0


def marcas_do_objetivo(id: int) -> list[str]:
    """Devolve as datas ISO em ordem determinística."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT data FROM objetivo_marcas "
            "WHERE objetivo_id = ? ORDER BY data",
            (id,),
        ).fetchall()
    return [row["data"] for row in rows]


# --- aprendizados (edificação mínima; P2 item 10) -----------------------------


_APRENDIZADO_STATUS = {"novo", "pratica", "aplicado", "arquivado"}
_APRENDIZADO_STATUS_MANUAL = {"novo", "aplicado", "arquivado"}


def add_aprendizado(
    texto: str,
    *,
    sensivel: bool = False,
    origem_captura_id: int | None = None,
) -> dict:
    """Registra um aprendizado; a origem torna retries da captura idempotentes."""
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO aprendizados "
            "(texto, sensivel, origem_captura_id, criado) "
            "VALUES (?, ?, ?, ?)",
            (texto, int(sensivel), origem_captura_id, time.time()),
        )

        if origem_captura_id is not None:
            row = con.execute(
                "SELECT * FROM aprendizados WHERE origem_captura_id = ?",
                (origem_captura_id,),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM aprendizados WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()

        con.commit()

    # O INSERT sem origem sempre cria uma linha; com origem, o SELECT recupera
    # tanto a nova linha quanto a linha preservada por um retry.
    assert row is not None
    return dict(row)


def list_aprendizados(status: str | None = None) -> list[dict]:
    """Lista aprendizados em ordem estável, com os mais recentes primeiro."""
    if status is not None and status not in _APRENDIZADO_STATUS:
        raise ValueError("status_aprendizado_invalido")

    sql = "SELECT * FROM aprendizados"
    params: tuple = ()
    if status is not None:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY criado DESC, id DESC"

    with closing(_connect()) as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_aprendizado(id: int) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM aprendizados WHERE id = ?",
            (id,),
        ).fetchone()
    return dict(row) if row is not None else None


def pratica_da_semana(semana: str) -> dict | None:
    """A prática ATUAL: só vale se foi escolhida para esta semana.

    `pratica_semana` era gravado e nunca comparado, então uma prática de julho
    seguia sendo anunciada como "prática da SEMANA" em agosto — todo dia, sem
    nunca perguntar se ele aplicou."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM aprendizados WHERE status = 'pratica' AND pratica_semana = ? "
            "ORDER BY pratica_em DESC LIMIT 1",
            (semana,),
        ).fetchone()
    return dict(row) if row else None


def praticas_sem_avaliacao(semana_atual: str) -> list[dict]:
    """Práticas de semanas ANTERIORES que continuam em aberto. A prática vencida não
    some: vira a pergunta "aplicou?" — senão o loop da edificação nunca fecha."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM aprendizados WHERE status = 'pratica' "
            "AND pratica_semana IS NOT NULL AND pratica_semana <> ? "
            "ORDER BY pratica_em DESC",
            (semana_atual,),
        ).fetchall()
    return [dict(row) for row in rows]


def definir_pratica(id: int, semana: str) -> dict | None:
    """Escolhe uma única prática ativa, sem alterar estado se o alvo for inválido."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        alvo = con.execute(
            "SELECT status FROM aprendizados WHERE id = ?",
            (id,),
        ).fetchone()
        if alvo is None or alvo["status"] == "arquivado":
            con.rollback()
            return None

        # Só a prática DA MESMA semana perde a vaga — é ela que está em disputa.
        # Rebaixar também as de semanas anteriores apagava a pergunta que
        # `praticas_sem_avaliacao` existe para fazer ("aplicou?"), e apagava
        # justamente quando ele fazia o que o review manda. Sem ele responder
        # nada: estado mudando sozinho é violação da lei 3. Mesmo defeito da fila
        # de melhorias (`escolher_melhoria`), fechado junto.
        con.execute(
            "UPDATE aprendizados "
            "SET status = 'novo', pratica_semana = NULL, pratica_em = NULL "
            "WHERE status = 'pratica' AND pratica_semana = ? AND id <> ?",
            (semana, id),
        )
        con.execute(
            "UPDATE aprendizados "
            "SET status = 'pratica', pratica_semana = ?, pratica_em = ? "
            "WHERE id = ?",
            (semana, time.time(), id),
        )
        row = con.execute(
            "SELECT * FROM aprendizados WHERE id = ?",
            (id,),
        ).fetchone()
        con.commit()

    return dict(row) if row is not None else None


def set_status_aprendizado(id: int, status: str) -> dict | None:
    """Aplica transições manuais; entrar em prática exige semana e usa outra função."""
    if status not in _APRENDIZADO_STATUS_MANUAL:
        raise ValueError("status_aprendizado_invalido")

    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE aprendizados "
            "SET status = ?, pratica_semana = NULL, pratica_em = NULL "
            "WHERE id = ?",
            (status, id),
        )
        if cur.rowcount == 0:
            con.commit()
            return None

        row = con.execute(
            "SELECT * FROM aprendizados WHERE id = ?",
            (id,),
        ).fetchone()
        con.commit()

    return dict(row) if row is not None else None


# --- melhorias (fila sem prazo; app / empresa / fluxo) ------------------------
#
# Fila separada das tarefas de propósito: melhoria não tem prazo, tem MOMENTO.
# No ClickUp ela cairia no bucket `backlog` da tela Tasks (days_overdue nulo) e
# morreria lá; nas áreas da triagem não há nenhuma que seja "o sistema".
#
# `app` é acionável só quando o Leo está programando comigo, então essas ficam
# FORA do "escolhe 1 da semana" — contá-las transformaria a fila em dívida.

_ALVO_MELHORIA = {"app", "empresa", "fluxo"}
_MELHORIA_STATUS = {"novo", "escolhida", "feita", "descartada"}
_MELHORIA_STATUS_MANUAL = {"novo", "feita", "descartada"}
# Alvos que o próprio Leo executa; `app` sai porque não depende dele sozinho.
_ALVO_DELE = ("empresa", "fluxo")


def _validar_alvo(alvo: str | None) -> None:
    """Alvo livre viraria taxonomia informal e a fila deixaria de ser filtrável."""
    if alvo is not None and alvo not in _ALVO_MELHORIA:
        raise ValueError("alvo_melhoria_invalido")


def add_melhoria(
    texto: str,
    *,
    alvo: str | None = None,
    sensivel: bool = False,
    origem_captura_id: int | None = None,
) -> dict:
    """Registra uma melhoria; a origem torna retries da captura idempotentes."""
    _validar_alvo(alvo)

    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO melhorias "
            "(texto, alvo, sensivel, origem_captura_id, criado) "
            "VALUES (?, ?, ?, ?, ?)",
            (texto, alvo, int(sensivel), origem_captura_id, time.time()),
        )

        if origem_captura_id is not None:
            row = con.execute(
                "SELECT * FROM melhorias WHERE origem_captura_id = ?",
                (origem_captura_id,),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM melhorias WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()

        con.commit()

    assert row is not None
    return dict(row)


def list_melhorias(
    alvo: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Lista em ordem estável, com as mais recentes primeiro."""
    _validar_alvo(alvo)
    if status is not None and status not in _MELHORIA_STATUS:
        raise ValueError("status_melhoria_invalido")

    sql = "SELECT * FROM melhorias"
    filtros: list[str] = []
    params: list = []
    if alvo is not None:
        filtros.append("alvo = ?")
        params.append(alvo)
    if status is not None:
        filtros.append("status = ?")
        params.append(status)
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    sql += " ORDER BY criado DESC, id DESC"

    with closing(_connect()) as con:
        rows = con.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_melhoria(id: int) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM melhorias WHERE id = ?",
            (id,),
        ).fetchone()
    return dict(row) if row is not None else None


def _melhorias_novas(condicao: str, params: tuple = ()) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT * FROM melhorias WHERE status = 'novo' AND {condicao} "
            "ORDER BY criado DESC, id DESC",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def melhorias_a_triar() -> list[dict]:
    """Sem alvo ainda. Na tela, o card delas só oferece os chips de alvo."""
    return _melhorias_novas("alvo IS NULL")


def melhorias_escolhiveis() -> list[dict]:
    """Já triadas para empresa/fluxo: são estas que aceitam "fazer esta semana".

    Separadas de `melhorias_a_triar` porque o review prometia "escolher 1" contando
    as duas, e o card de "a triar" não tem esse botão — o texto mandava o Leo
    procurar uma ação que aquela seção não oferece."""
    return _melhorias_novas(
        f"alvo IN ({', '.join('?' for _ in _ALVO_DELE)})",
        _ALVO_DELE,
    )


def melhoria_da_semana(semana: str) -> dict | None:
    """A escolhida DESTA semana — a de outra semana não conta.

    `escolhida_semana` era gravada e nunca comparada: o mesmo defeito que
    `pratica_da_semana` (acima) existe para consertar. Sem o filtro, uma escolha de
    junho seguia anunciada como "a melhoria desta semana" em agosto, e como a tela
    usa ternário encadeado (escolhida ? … : paradas ? …), o convite "escolher 1"
    nunca mais era renderizado. A fila travava em silêncio."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM melhorias WHERE status = 'escolhida' AND escolhida_semana = ? "
            "ORDER BY escolhida_em DESC LIMIT 1",
            (semana,),
        ).fetchone()
    return dict(row) if row else None


def melhorias_vencidas(semana_atual: str) -> list[dict]:
    """Escolhas de semanas ANTERIORES ainda em aberto — viram a pergunta "fez?".

    Não se apaga a escolha na virada da semana: apagar seria o sistema decidindo
    por ele (lei 3). Ela sai do lugar de "compromisso desta semana" e vira uma
    pergunta, exatamente como `praticas_sem_avaliacao` faz na edificação.

    Alvo `app` fica de fora como em todo o resto da cobrança. `escolher_melhoria`
    já recusa app, mas `definir_alvo` é UPDATE puro e aceita qualquer status: dá
    para escolher como empresa e re-triar para app depois. Sem este filtro, essa
    linha viraria cobrança semanal perpétua no artefato do vault e no lockscreen
    por algo que ele não faz sozinho."""
    marcadores = ", ".join("?" for _ in _ALVO_DELE)
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM melhorias WHERE status = 'escolhida' "
            "AND escolhida_semana IS NOT NULL AND escolhida_semana <> ? "
            f"AND (alvo IS NULL OR alvo IN ({marcadores})) "
            "ORDER BY escolhida_em DESC",
            (semana_atual, *_ALVO_DELE),
        ).fetchall()
    return [dict(row) for row in rows]


def definir_alvo(id: int, alvo: str) -> dict | None:
    """Triagem da fila: um toque, sem obrigar a decidir na hora da captura."""
    _validar_alvo(alvo)

    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE melhorias SET alvo = ? WHERE id = ?",
            (alvo, id),
        )
        if cur.rowcount == 0:
            con.commit()
            return None

        row = con.execute(
            "SELECT * FROM melhorias WHERE id = ?",
            (id,),
        ).fetchone()
        con.commit()

    return dict(row) if row is not None else None


def escolher_melhoria(id: int, semana: str) -> dict | None:
    """Escolhe UMA melhoria para a semana; duas escolhas valem tanto quanto nenhuma.

    Só `novo`/`escolhida` entram: reabrir uma feita ou descartada desfaria uma
    decisão que ele já tomou. Alvo `app` também não entra — a vaga é do que ELE
    faz na semana, e a tela promete no próprio grupo que as de app não entram na
    conta do review."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        atual = con.execute(
            "SELECT status, alvo FROM melhorias WHERE id = ?",
            (id,),
        ).fetchone()
        if (
            atual is None
            or atual["status"] not in ("novo", "escolhida")
            or atual["alvo"] == "app"
        ):
            con.rollback()
            return None

        # Só a escolha DA MESMA semana perde a vaga — é ela que está em disputa.
        # Rebaixar também as de semanas anteriores destruía a pergunta "fez?"
        # justamente quando ele fazia o que o review manda, e sem ele responder
        # nada: estado mudando sozinho é violação da lei 3.
        con.execute(
            "UPDATE melhorias "
            "SET status = 'novo', escolhida_semana = NULL, escolhida_em = NULL "
            "WHERE status = 'escolhida' AND escolhida_semana = ? AND id <> ?",
            (semana, id),
        )
        con.execute(
            "UPDATE melhorias "
            "SET status = 'escolhida', escolhida_semana = ?, escolhida_em = ? "
            "WHERE id = ?",
            (semana, time.time(), id),
        )
        row = con.execute(
            "SELECT * FROM melhorias WHERE id = ?",
            (id,),
        ).fetchone()
        con.commit()

    return dict(row) if row is not None else None


def set_status_melhoria(id: int, status: str) -> dict | None:
    """Transições manuais; `escolhida` exige semana e usa escolher_melhoria."""
    if status not in _MELHORIA_STATUS_MANUAL:
        raise ValueError("status_melhoria_invalido")

    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE melhorias "
            "SET status = ?, escolhida_semana = NULL, escolhida_em = NULL "
            "WHERE id = ?",
            (status, id),
        )
        if cur.rowcount == 0:
            con.commit()
            return None

        row = con.execute(
            "SELECT * FROM melhorias WHERE id = ?",
            (id,),
        ).fetchone()
        con.commit()

    return dict(row) if row is not None else None


# --- anki_cards (P2 item 12) --------------------------------------------------
# Lei 3 no dado: a IA cria SÓ status='sugerido'; aprovado/descartado são decisões
# do Leo (update); 'exportado' é EXCLUSIVO da transação de export.


_ANKI_STATUS = {"sugerido", "aprovado", "descartado", "exportado", "exporting"}
_ANKI_STATUS_EDITAVEIS = {"sugerido", "aprovado", "descartado"}
_ANKI_CAMPOS_EDITAVEIS = {
    "frente",
    "meaning",
    "example",
    "hook",
    "deck",
    "status",
}
_ANKI_CAMPOS_TEXTO = {"frente", "meaning", "example", "hook", "deck"}


def _normalizar_anki_cards(cards: list[dict]) -> list[dict]:
    normalizados: list[dict] = []
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("card_anki_invalido")

        frente = card.get("frente")
        if not isinstance(frente, str) or not frente.strip():
            raise ValueError("frente_vazia")

        normalizado = {"frente": frente}
        for campo in ("meaning", "example", "hook"):
            valor = card.get(campo, "")
            if not isinstance(valor, str):
                raise ValueError(f"{campo}_invalido")
            normalizado[campo] = valor

        normalizados.append(normalizado)

    return normalizados


def _insert_anki_cards(
    con: sqlite3.Connection,
    cards: list[dict],
    session_id: int | None,
    deck: str = "",
) -> list[dict]:
    """O deck vem por PARÂMETRO, nunca como chave do card.

    `_normalizar_anki_cards` descarta chaves desconhecidas de propósito: o dict vem
    da proposta do modelo, e o modelo não tem autoridade para escolher deck — se
    tivesse, uma injeção na leitura direcionaria cards para qualquer lugar.
    """
    criado = time.time()
    criados: list[dict] = []
    for card in cards:
        cur = con.execute(
            "INSERT INTO anki_cards "
            "(session_id, frente, meaning, example, hook, deck, criado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                card["frente"],
                card["meaning"],
                card["example"],
                card["hook"],
                deck,
                criado,
            ),
        )
        row = con.execute(
            "SELECT * FROM anki_cards WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        if row is not None:
            criados.append(dict(row))
    return criados


def add_anki_cards(
    cards: list[dict],
    session_id: int | None = None,
    deck: str = "",
) -> list[dict]:
    """Persiste propostas em lote, sempre aguardando aprovação explícita posterior."""
    normalizados = _normalizar_anki_cards(cards)
    if not normalizados:
        return []
    with closing(_connect()) as con:
        criados = _insert_anki_cards(con, normalizados, session_id, deck)
        con.commit()
    return criados


def list_anki_cards_for_session(session_id: int) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM anki_cards WHERE session_id = ? ORDER BY criado, id",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def claim_anki_suggestion(session_id: int) -> str:
    """Retorna claimed/done/processing e impede dois modelos para a mesma sessão."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT status FROM anki_suggestion_runs WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is not None:
            if (
                row["status"] == "processing"
                and float(row["updated"]) < time.time() - CLAIM_STALE_SECONDS
            ):
                agora = time.time()
                con.execute(
                    "UPDATE anki_suggestion_runs SET created = ?, updated = ? "
                    "WHERE session_id = ?",
                    (agora, agora, session_id),
                )
                con.commit()
                return "claimed"
            con.commit()
            return str(row["status"])
        agora = time.time()
        con.execute(
            "INSERT INTO anki_suggestion_runs (session_id, status, created, updated) "
            "VALUES (?, 'processing', ?, ?)",
            (session_id, agora, agora),
        )
        con.commit()
        return "claimed"


def finish_anki_suggestion(
    session_id: int, cards: list[dict], deck: str = ""
) -> list[dict]:
    """Cards e receipt done entram na mesma transação, inclusive quando cards=[]."""
    normalizados = _normalizar_anki_cards(cards)
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT status FROM anki_suggestion_runs WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None or row["status"] != "processing":
            con.rollback()
            raise ValueError("anki_suggestion_sem_claim")
        criados = _insert_anki_cards(con, normalizados, session_id, deck)
        con.execute(
            "UPDATE anki_suggestion_runs SET status = 'done', updated = ? "
            "WHERE session_id = ?",
            (time.time(), session_id),
        )
        con.commit()
        return criados


def release_anki_suggestion(session_id: int) -> None:
    with closing(_connect()) as con:
        con.execute(
            "DELETE FROM anki_suggestion_runs "
            "WHERE session_id = ? AND status = 'processing'",
            (session_id,),
        )
        con.commit()


def list_anki_cards(status: str | None = None) -> list[dict]:
    """Lista propostas sem expor o conteúdo em logs ou telemetria."""
    if status is not None and status not in _ANKI_STATUS:
        raise ValueError("status_anki_invalido")

    query = "SELECT * FROM anki_cards"
    params: tuple = ()
    if status is not None:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY criado DESC, id DESC"

    with closing(_connect()) as con:
        rows = con.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_anki_card(id: int) -> dict | None:
    """Obtém um candidato pelo identificador, sem registrar seu conteúdo."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM anki_cards WHERE id = ?",
            (id,),
        ).fetchone()

    return dict(row) if row is not None else None


def update_anki_card(id: int, **campos) -> dict | None:
    """Aplica somente edições e decisões manuais permitidas pela lei 3."""
    desconhecidos = set(campos) - _ANKI_CAMPOS_EDITAVEIS
    if desconhecidos:
        raise ValueError("campo_anki_invalido")

    if "status" in campos and campos["status"] not in _ANKI_STATUS_EDITAVEIS:
        # Exportado é reservado à transação de exportação para evitar duplicidade.
        raise ValueError("status_anki_invalido")

    for campo in set(campos) & _ANKI_CAMPOS_TEXTO:
        if not isinstance(campos[campo], str):
            raise ValueError(f"{campo}_invalido")

    if "frente" in campos and not campos["frente"].strip():
        raise ValueError("frente_vazia")

    if not campos:
        return get_anki_card(id)

    atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)
    valores = [campos[campo] for campo in campos]
    valores.append(id)

    with closing(_connect()) as con:
        cur = con.execute(
            f"UPDATE anki_cards SET {atribuicoes} "
            "WHERE id = ? AND status IN ('sugerido', 'aprovado', 'descartado')",
            valores,
        )
        if cur.rowcount == 0:
            existente = con.execute(
                "SELECT 1 FROM anki_cards WHERE id = ?",
                (id,),
            ).fetchone()
            con.commit()
            if existente is None:
                return None
            raise ValueError("anki_card_bloqueado")

        row = con.execute(
            "SELECT * FROM anki_cards WHERE id = ?",
            (id,),
        ).fetchone()
        con.commit()

    return dict(row) if row is not None else None


def claim_anki_export() -> list[dict]:
    """Reserva sem afirmar entrega; falha de arquivo devolve os cards a aprovado."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        agora = time.time()
        con.execute(
            "UPDATE anki_cards SET status = 'aprovado', export_claimed = NULL "
            "WHERE status = 'exporting' "
            "AND (export_claimed IS NULL OR export_claimed < ?)",
            (agora - CLAIM_STALE_SECONDS,),
        )
        rows = con.execute(
            "SELECT * FROM anki_cards "
            "WHERE status = 'aprovado' "
            "ORDER BY criado ASC, id ASC"
        ).fetchall()

        if rows:
            con.execute(
                "UPDATE anki_cards "
                "SET status = 'exporting', export_claimed = ? "
                "WHERE status = 'aprovado'",
                (agora,),
            )

        con.commit()

    return [dict(row) for row in rows]


def finish_anki_export(card_ids: list[int], *, success: bool) -> None:
    if not card_ids:
        return
    placeholders = ",".join("?" for _ in card_ids)
    destino = "exportado" if success else "aprovado"
    with closing(_connect()) as con:
        con.execute(
            f"UPDATE anki_cards SET status = ?, export_claimed = NULL "
            f"WHERE status = 'exporting' AND id IN ({placeholders})",
            (destino, *card_ids),
        )
        con.commit()


# --- backup do banco ----------------------------------------------------------
#
# `data.db` guarda o que o vault NÃO guarda: pontos, nível, rotinas, checks do
# dia, aprendizados, melhorias, fila de captura. Não havia backup nenhum — um
# snapshot manual de 12/jul e mais nada. E `data.db*` está no `.gitignore`, então
# nem o push do repositório cobre.
#
# O nível é vitalício por desenho (lei 4: não regride). Um disco ruim tornaria
# essa promessa mentira, e a série de checks diários não existe em lugar nenhum
# para reconstruir.

_MANTER_BACKUPS = 14


def fazer_backup(destino: Path | str, *, hoje: str, manter: int = _MANTER_BACKUPS):
    """Snapshot do banco em `destino/data-<hoje>.db`. Devolve o caminho ou None.

    Usa a API online do SQLite, não cópia de arquivo: o BFF escreve enquanto o
    backup roda, e copiar por baixo produz snapshot rasgado no meio de uma
    transação.

    Um arquivo por dia, sobrescrito — o worker roda várias vezes ao dia e um
    arquivo por execução encheria o disco sem dizer mais nada que "o estado mais
    recente daquele dia".

    Nunca levanta: o backup é rede de segurança e não pode ser o motivo de o BFF
    cair. Falha vira log e None."""
    parcial = None
    try:
        pasta = Path(destino)
        pasta.mkdir(parents=True, exist_ok=True)

        with closing(_connect()) as origem:
            # Integridade ANTES de sobrescrever: copiar lixo por cima do último
            # estado bom é pior que não fazer backup, e o erro só apareceria no
            # dia em que ele precisasse do arquivo.
            veredito = origem.execute("PRAGMA integrity_check").fetchone()[0]
            if veredito != "ok":
                logger.error("backup abortado: integrity_check falhou")
                return None

            alvo = pasta / f"data-{hoje}.db"
            parcial = pasta / f"data-{hoje}.db.parcial"
            with closing(sqlite3.connect(parcial)) as copia:
                origem.backup(copia)
        # Só troca o arquivo bom depois que a cópia inteira terminou.
        parcial.replace(alvo)

        antigos = sorted(pasta.glob("data-*.db"))
        for velho in antigos[:-manter] if manter > 0 else antigos:
            velho.unlink(missing_ok=True)
        return alvo
    except Exception as e:  # noqa: BLE001 — rede de segurança nunca derruba o app
        logger.warning("backup falhou: %s", type(e).__name__)
        # Meio-arquivo na pasta se passa por backup e não restaura.
        if parcial is not None:
            parcial.unlink(missing_ok=True)
        return None

import itertools
import time
from pathlib import Path

from app import capture_pipeline, config, store, vault_client

# unico tambem ENTRE execucoes: o db do conftest persiste entre rodadas do pytest
_seq = itertools.count()
_RUN = time.time_ns()


def _insert_capture(text: str = "conteúdo de teste") -> int:
    con = store._connect()
    try:
        cursor = con.execute(
            """
            INSERT INTO capture_queue
                (ts, text, profile, client_key, status, attempts)
            VALUES
                (?, ?, ?, ?, 'pending', 0)
            """,
            (1.0, text, "Capturas", f"teste-{_RUN}-{next(_seq)}"),
        )
        con.commit()
        return cursor.lastrowid
    finally:
        con.close()


def _capture(cid: int):
    con = store._connect()
    try:
        return con.execute(
            "SELECT * FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()
    finally:
        con.close()


async def test_vault_sem_config_preserva_fila_e_interrompe_tick(monkeypatch):
    primeiro = _insert_capture("primeiro")
    segundo = _insert_capture("segundo")

    async def falha_sem_config(*args, **kwargs):
        raise vault_client.VaultError("vault_nao_configurado")

    monkeypatch.setattr(vault_client, "write_raw", falha_sem_config)

    assert await capture_pipeline.process_pending() == 0

    row_primeiro = _capture(primeiro)
    assert row_primeiro["status"] == "pending"
    assert row_primeiro["attempts"] == 0
    assert row_primeiro["last_error"] == "VaultError"

    row_segundo = _capture(segundo)
    assert row_segundo["status"] == "pending"
    assert row_segundo["attempts"] == 0
    assert row_segundo["last_error"] is None


async def test_outro_erro_do_vault_incrementa_attempts(monkeypatch):
    cid = _insert_capture()

    async def falha_transitoria(*args, **kwargs):
        raise vault_client.VaultError("PUT x: 500")

    monkeypatch.setattr(vault_client, "write_raw", falha_transitoria)

    assert await capture_pipeline.process_pending() == 0

    row = _capture(cid)
    assert row["status"] == "pending"
    assert row["attempts"] == 1
    assert row["last_error"] == "VaultError"


def test_done_limpa_erro_anterior():
    cid = _insert_capture()
    store.mark_capture(cid, error="VaultError")

    store.mark_capture(cid, status="done")

    row = _capture(cid)
    assert row["status"] == "done"
    assert row["last_error"] is None


def test_done_com_erro_explicito_preserva_erro_passado():
    cid = _insert_capture()
    store.mark_capture(cid, error="ErroAnterior")

    store.mark_capture(cid, status="done", error="ErroFinal")

    row = _capture(cid)
    assert row["status"] == "done"
    assert row["last_error"] == "ErroFinal"


def test_db_path_default_e_absoluto_e_ancorado_no_bff():
    db_path = Path(config.Settings(_env_file=None).db_path)
    raiz_bff = Path(config.__file__).resolve().parent.parent

    assert db_path.is_absolute()
    assert db_path == raiz_bff / "data.db"

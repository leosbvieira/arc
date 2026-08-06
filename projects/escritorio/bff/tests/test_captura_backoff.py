"""Uma instabilidade de 30s não pode queimar a captura.

MAX_ATTEMPTS=5 e o worker roda a cada 5s, sem backoff: 25 segundos de Hermes
instável — que a própria tela Hoje tornava provável — consumiam as 5 tentativas e
jogavam a captura para `failed`. De lá ela só voltava com RESTART do BFF, porque
`retry_failed_captures` só é chamado no startup.

A lei 1 ("nada se perde") era respeitada na letra (o item fica no banco) e violada
no espírito: ficava invisível até alguém reiniciar o servidor.
"""
import time

import pytest

from app import store
from app.config import settings


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()


def test_item_que_acabou_de_falhar_espera_antes_de_voltar():
    cid = store.enqueue_capture("pagar o Inter", None, None)
    store.mark_capture(cid, error="hermes_error", bump_attempts=True)

    assert store.pending_captures() == [], "tentar de novo em 5s desperdiça a tentativa"


def test_espera_cresce_a_cada_tentativa():
    cid = store.enqueue_capture("x", None, None)

    store.mark_capture(cid, error="hermes_error", bump_attempts=True)
    primeira = store.proxima_tentativa_em(cid)
    store.mark_capture(cid, error="hermes_error", bump_attempts=True)
    segunda = store.proxima_tentativa_em(cid)

    assert segunda > primeira, "backoff tem que crescer, senão queima o orçamento"


def test_depois_da_espera_o_item_volta():
    cid = store.enqueue_capture("x", None, None)
    store.mark_capture(cid, error="hermes_error", bump_attempts=True)

    # simula o tempo passando
    with store._connect() as con:
        con.execute("UPDATE capture_queue SET proxima_em = ? WHERE id = ?", (time.time() - 1, cid))
        con.commit()

    assert [c["id"] for c in store.pending_captures()] == [cid]


def test_falha_definitiva_ainda_sai_da_fila_ativa():
    """O teto continua valendo: depois de MAX_ATTEMPTS vira `failed` e não gira à toa."""
    cid = store.enqueue_capture("x", None, None)
    for _ in range(store.MAX_ATTEMPTS):
        store.mark_capture(cid, error="hermes_error", bump_attempts=True)

    with store._connect() as con:
        status = con.execute("SELECT status FROM capture_queue WHERE id = ?", (cid,)).fetchone()[0]
    assert status == "failed"


def test_failed_volta_sozinho_depois_de_um_tempo():
    """`retry_failed_captures` só era chamado no startup: sem reiniciar o BFF, uma
    captura em `failed` ficava invisível para sempre. Lei 1 na letra, violada no
    espírito."""
    cid = store.enqueue_capture("nao pode sumir", None, None)
    for _ in range(store.MAX_ATTEMPTS):
        store.mark_capture(cid, error="hermes_error", bump_attempts=True)

    # nada volta enquanto a falha é recente
    assert store.reapresentar_failed(idade_minima_s=3600) == 0

    with store._connect() as con:
        con.execute("UPDATE capture_queue SET proxima_em = ? WHERE id = ?", (time.time() - 7200, cid))
        con.commit()

    assert store.reapresentar_failed(idade_minima_s=3600) == 1
    with store._connect() as con:
        status = con.execute("SELECT status FROM capture_queue WHERE id = ?", (cid,)).fetchone()[0]
    assert status == "pending"

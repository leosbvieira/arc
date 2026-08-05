"""A "prática da SEMANA" tem que ser desta semana.

`pratica_semana` era gravado e nunca comparado: `list_aprendizados(status="pratica")`
não filtra por semana e os dois consumidores pegam `praticas[0]`. Resultado: uma
prática escolhida em 12/jul continuava sendo anunciada como "prática da semana" em
agosto — todo dia, sem nunca perguntar se ele aplicou.

É a dor original do Leo ("aprendo hacks e esqueço de aplicar") com UI por cima.
"""
from datetime import timedelta

import pytest

from app import agenda, store, tasks, tz
from app.config import settings


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    store.init_db()


def _aprendizado(texto: str) -> int:
    return store.add_aprendizado(texto)["id"]


def _semana(delta_semanas: int = 0) -> str:
    return agenda.semana_iso(tz.hoje_local() + timedelta(weeks=delta_semanas))


def test_pratica_desta_semana_aparece():
    store.definir_pratica(_aprendizado("dormir com o livro na mesa"), _semana())

    assert store.pratica_da_semana(_semana()) is not None


def test_pratica_da_semana_passada_nao_aparece_como_atual():
    store.definir_pratica(_aprendizado("prática velha"), _semana(-1))

    assert store.pratica_da_semana(_semana()) is None


def test_pratica_vencida_fica_pendente_de_resposta():
    """Ela não some: vira a pergunta "aplicou?" — senão o loop nunca fecha."""
    id_ = _aprendizado("prática velha")
    store.definir_pratica(id_, _semana(-1))

    pendentes = store.praticas_sem_avaliacao(_semana())
    assert [p["id"] for p in pendentes] == [id_]


def test_digest_nao_anuncia_pratica_de_outra_semana():
    store.definir_pratica(_aprendizado("prática de julho"), _semana(-3))

    linhas = tasks.routine_lines()
    assert not any("prática" in linha.lower() for linha in linhas)

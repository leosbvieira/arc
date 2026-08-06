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


def test_escolher_a_pratica_da_semana_nao_apaga_a_pratica_vencida():
    """A vaga em disputa é a DESTA semana, não a história.

    `praticas_sem_avaliacao` existe para transformar a prática vencida na pergunta
    "aplicou?" — mas `definir_pratica` rebaixava QUALQUER outra linha em prática,
    inclusive as de semanas anteriores. A pergunta era destruída exatamente quando
    ele fazia o que o review manda (escolher a prática da semana), sem ele
    responder nada: estado mudando sozinho é violação da lei 3.

    Mesmo defeito encontrado na fila de melhorias; os dois foram fechados juntos."""
    antiga = _aprendizado("perguntar antes de prometer")
    store.definir_pratica(antiga, _semana(-6))
    nova = _aprendizado("escrever o combinado no mesmo dia")

    store.definir_pratica(nova, _semana())

    sobreviveu = store.get_aprendizado(antiga)
    assert sobreviveu["status"] == "pratica"
    assert sobreviveu["pratica_semana"] == _semana(-6)
    assert [p["id"] for p in store.praticas_sem_avaliacao(_semana())] == [antiga]
    assert store.pratica_da_semana(_semana())["id"] == nova


def test_trocar_de_pratica_na_mesma_semana_ainda_substitui():
    """A disputa pela vaga da semana corrente continua valendo — uma por vez."""
    primeira = _aprendizado("primeira")
    segunda = _aprendizado("segunda")

    store.definir_pratica(primeira, _semana())
    store.definir_pratica(segunda, _semana())

    assert store.get_aprendizado(primeira)["status"] == "novo"
    assert store.get_aprendizado(primeira)["pratica_semana"] is None
    assert store.pratica_da_semana(_semana())["id"] == segunda

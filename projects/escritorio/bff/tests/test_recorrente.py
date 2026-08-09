"""A tag `recorrente`: como o app fica sabendo que uma obrigação volta.

O ClickUp tem recorrência nativa na UI web, mas **não a devolve pela API** — nem
em `GET /list/{id}/task`, nem em `GET /task/{id}` (schema conferido em 09/ago/2026:
a resposta traz `due_date`, `tags`, `priority`, `custom_fields` e mais trinta
campos, e nenhum deles é recorrência). Sem uma marca própria, "Unimed" concluída
some da tela como uma tarefa qualquer, e nada diz que ela volta dia 20.

A marca é uma tag, lida pelo mesmo caminho que a tag `sensivel` já usava.
"""
from app.tasks import _display, _from_clickup


def _task(**extra) -> dict:
    return {"id": "abc123", "name": "Unimed", "_area": "Finance", **extra}


def test_tag_recorrente_atravessa_ate_o_contrato_do_app():
    saida = _display(_from_clickup(_task(tags=[{"name": "recorrente"}])))
    assert saida.recorrente is True


def test_sem_a_tag_a_tarefa_nao_e_recorrente():
    assert _display(_from_clickup(_task(tags=[]))).recorrente is False
    assert _display(_from_clickup(_task())).recorrente is False


def test_acento_e_caixa_nao_mudam_a_leitura():
    """Mesma normalização da `sensivel`: quem digita a tag na UI é humano."""
    for escrita in ("Recorrente", "RECORRENTE", "recorrênte"):
        saida = _display(_from_clickup(_task(tags=[{"name": escrita}])))
        assert saida.recorrente is True, escrita


def test_tag_em_string_crua_tambem_conta():
    """O ClickUp devolve dicts, mas o mapeador aceita string — não quebra se mudar."""
    assert _display(_from_clickup(_task(tags=["recorrente"]))).recorrente is True


def test_recorrente_e_sensivel_sao_independentes():
    """Uma consulta médica recorrente é as duas coisas; nenhuma anula a outra."""
    saida = _display(
        _from_clickup(_task(tags=[{"name": "recorrente"}, {"name": "sensivel"}]))
    )
    assert (saida.recorrente, saida.sensivel) == (True, True)

    so_sensivel = _display(_from_clickup(_task(tags=[{"name": "sensivel"}])))
    assert (so_sensivel.recorrente, so_sensivel.sensivel) == (False, True)


def test_outras_tags_nao_viram_recorrente():
    saida = _display(_from_clickup(_task(tags=[{"name": "recorrencia"}])))
    assert saida.recorrente is False

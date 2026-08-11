"""A triagem nunca moveu nada, e o motivo era estrutural.

`move_task` adicionava a tarefa na lista de destino e tentava removê-la da origem.
A origem, porém, é a HOME LIST da tarefa — e o ClickUp recusa removê-la:

    DELETE /list/{staging}/task/{id}
    400 {"err": "Task home list cannot be altered", "ECODE": "TASK_035"}

O add respondia 200, então a tarefa ficava nas DUAS listas e a triagem reportava
falha sem dizer qual. Confirmado contra o workspace real em 2026-08-10. A troca de
home list existe só na v3, e é o que estes testes fixam.
"""
import httpx
import pytest

from app import clickup_client


class _Gravador:
    """Registra (método, url) de cada chamada e devolve a resposta programada."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.chamadas: list[tuple[str, str]] = []

    def _responder(self, metodo, url):
        self.chamadas.append((metodo, url))
        return self.respostas[metodo]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, *, params=None, headers=None):
        return self._responder("GET", url)

    async def put(self, url, *, headers=None, json=None):
        return self._responder("PUT", url)

    async def post(self, url, *, headers=None, json=None):
        return self._responder("POST", url)

    async def delete(self, url, *, headers=None):
        return self._responder("DELETE", url)


def _resposta(status, corpo):
    return httpx.Response(status, json=corpo, request=httpx.Request("GET", "http://x"))


@pytest.fixture
def gravador(monkeypatch):
    tarefa = {
        "id": "86ajyxf53",
        "team_id": "9007178855",
        "list": {"id": "901327803429", "name": "Staging"},
    }
    gravado = _Gravador(
        {
            "GET": _resposta(200, tarefa),
            "PUT": _resposta(200, {}),
            "POST": _resposta(200, {}),
            "DELETE": _resposta(200, {}),
        }
    )
    monkeypatch.setattr(
        clickup_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: gravado,
    )
    return gravado


async def test_move_usa_o_endpoint_de_home_list_da_v3(gravador):
    assert await clickup_client.move_task("86ajyxf53", "901327729099") is True

    metodo, url = gravador.chamadas[-1]
    assert metodo == "PUT"
    assert url == (
        "https://api.clickup.com/api/v3/workspaces/9007178855"
        "/tasks/86ajyxf53/home_list/901327729099"
    )


async def test_o_workspace_sai_da_propria_tarefa(gravador):
    """Sem isto seria preciso uma configuração nova só para montar a URL — e uma
    configuração a mais é uma a mais para estar errada no dia da mudança."""
    await clickup_client.move_task("86ajyxf53", "901327729099")

    assert "/workspaces/9007178855/" in gravador.chamadas[-1][1]


async def test_nao_tenta_mais_remover_a_tarefa_da_home_list(gravador):
    """O DELETE era o passo que estourava TASK_035 em toda triagem. Se alguém
    reintroduzir o add+remove, este teste cai."""
    await clickup_client.move_task("86ajyxf53", "901327729099")

    metodos = [metodo for metodo, _ in gravador.chamadas]
    assert "DELETE" not in metodos
    # E o add do ClickApp também sai: ele é o que criava a segunda lista.
    assert "POST" not in metodos


async def test_falha_do_move_sobe_para_o_chamador(monkeypatch):
    """`aplicar_triagem` isola a falha por tarefa e reporta o nome da classe. Se o
    move engolir o erro, a triagem volta a mentir que deu certo."""
    tarefa = {"id": "t1", "team_id": "9007178855", "list": {"id": "l0"}}
    gravado = _Gravador(
        {
            "GET": _resposta(200, tarefa),
            "PUT": _resposta(400, {"err": "Status not found", "ECODE": "TASK_XXX"}),
        }
    )
    monkeypatch.setattr(
        clickup_client.httpx,
        "AsyncClient",
        lambda *args, **kwargs: gravado,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await clickup_client.move_task("t1", "l1")

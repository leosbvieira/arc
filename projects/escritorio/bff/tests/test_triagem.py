from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import clickup_client, hermes_client, store, tasks
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


async def test_propose_triage_com_lote_vazio_nao_chama_o_hermes(monkeypatch):
    """Sem item para triar não há o que perguntar. O curto-circuito existia só para
    `hermes_mock`, então em produção (Hermes real) a Home pagava uma chamada de LLM
    inteira — ~8,5s medidos — para classificar zero itens, estourando o timeout de
    6s da tela e acendendo "alguns dados não responderam" em TODA carga."""
    monkeypatch.setattr(settings, "hermes_mock", False)
    chamadas = []

    async def fake_oneshot(prompt):
        chamadas.append(prompt)
        return "[]"

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    assert await hermes_client.propose_triage([], areas=["Trabalho"]) == []
    assert chamadas == []


async def test_propose_triage_envia_lote_e_extrai_json(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)
    chamadas = []

    async def fake_oneshot(prompt):
        chamadas.append(prompt)
        return (
            'resposta: [{"id":"s1","area":"Trabalho"},'
            '{"id":"s2","area":null},{"area":"Corpo"}]'
        )

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    resultado = await hermes_client.propose_triage(
        [
            {"id": "s1", "titulo": "Preparar relatório"},
            {"id": "s2", "titulo": "Marcar consulta"},
        ],
        areas=["Trabalho", "Corpo"],
    )

    assert resultado == [
        {"id": "s1", "area": "Trabalho"},
        {"id": "s2", "area": None},
    ]
    assert len(chamadas) == 1
    prompt = chamadas[0]
    # rsplit: a prosa do frame também menciona <staging>; o bloco real é o último.
    conteudo = prompt.rsplit("<staging>", 1)[1].split("</staging>", 1)[0]
    assert "s1 | Preparar relatório" in conteudo
    assert "s2 | Marcar consulta" in conteudo
    assert '"Trabalho"' in prompt
    assert '"Corpo"' in prompt


async def test_propose_triage_sem_json_falha_sem_payload(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)

    async def fake_oneshot(_prompt):
        return "Não há uma proposta estruturada."

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    with pytest.raises(RuntimeError, match=r"^triage_sem_json$"):
        await hermes_client.propose_triage(
            [{"id": "s1", "titulo": "Conteúdo sensível"}],
            areas=["Trabalho"],
        )


async def test_triagem_pack_filtra_staging_e_valida_propostas(monkeypatch):
    agora_ms = str(
        int(datetime.now(timezone.utc).timestamp() * 1000)
    )
    staging_valido = tasks._Task("s1", "Primeiro", "Staging")
    staging_invalido = tasks._Task("s2", "Segundo", "Staging")
    trabalho = tasks._Task("t1", "Terceiro", "Trabalho")
    raw = [
        {"id": "s1", "date_created": agora_ms},
        {"id": "s2", "date_created": agora_ms},
        {"id": "t1", "date_created": agora_ms},
    ]

    async def fake_source():
        return [staging_valido, staging_invalido, trabalho], raw

    async def fake_propose(itens, areas):
        assert itens == [
            {"id": "s1", "titulo": "Primeiro"},
            {"id": "s2", "titulo": "Segundo"},
        ]
        assert areas == tasks.AREAS_TRIAGEM
        return [
            {"id": "s1", "area": "Trabalho"},
            {"id": "s2", "area": "Inexistente"},
        ]

    monkeypatch.setattr(tasks, "_source", fake_source)
    monkeypatch.setattr(
        hermes_client,
        "propose_triage",
        fake_propose,
    )

    pack = await tasks.triagem_pack()

    assert pack == {
        "itens": [
            {
                "id": "s1",
                "name": "Primeiro",
                "idade_d": tasks._age_days(agora_ms),
                "area_proposta": "Trabalho",
            },
            {
                "id": "s2",
                "name": "Segundo",
                "idade_d": tasks._age_days(agora_ms),
                "area_proposta": None,
            },
        ],
        "n": 2,
    }


async def test_triagem_pack_degrada_quando_hermes_falha(monkeypatch):
    staging_a = tasks._Task("s1", "Primeiro", "Staging")
    staging_b = tasks._Task("s2", "Segundo", "Staging")

    async def fake_source():
        return [staging_a, staging_b], []

    async def fake_propose(_itens, areas):
        assert areas == tasks.AREAS_TRIAGEM
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(tasks, "_source", fake_source)
    monkeypatch.setattr(
        hermes_client,
        "propose_triage",
        fake_propose,
    )

    pack = await tasks.triagem_pack()

    assert pack["n"] == 2
    assert [
        item["area_proposta"] for item in pack["itens"]
    ] == [None, None]


def test_get_triagem_retorna_shape_correto(client, monkeypatch):
    staging = tasks._Task("staging-get", "Captura nova", "Staging")
    monkeypatch.setattr(tasks, "_MOCK", [*tasks._MOCK, staging])

    async def fake_propose(itens, areas):
        assert itens == [
            {"id": "staging-get", "titulo": "Captura nova"}
        ]
        assert areas == tasks.AREAS_TRIAGEM
        return [{"id": "staging-get", "area": "Estudo"}]

    monkeypatch.setattr(
        hermes_client,
        "propose_triage",
        fake_propose,
    )

    response = client.get("/triagem")

    assert response.status_code == 200
    assert response.json() == {
        "itens": [
            {
                "id": "staging-get",
                "name": "Captura nova",
                "idade_d": None,
                "area_proposta": "Estudo",
            }
        ],
        "n": 1,
    }


def test_post_triagem_aplicar_mock_e_validacoes(client, monkeypatch):
    staging = tasks._Task(
        "staging-post",
        "Captura aprovada",
        "Staging",
    )
    monkeypatch.setattr(tasks, "_MOCK", [*tasks._MOCK, staging])

    response = client.post(
        "/triagem/aplicar",
        json={
            "movimentos": [
                {"task_id": "staging-post", "area": "Corpo"},
                {"task_id": "desconhecida", "area": "Finance"},
                {"task_id": "t1", "area": "Estudo"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "resultados": [
            {
                "task_id": "staging-post",
                "ok": True,
                "erro": None,
            },
            {
                "task_id": "desconhecida",
                "ok": False,
                "erro": "nao_encontrado",
            },
            {
                "task_id": "t1",
                "ok": False,
                "erro": "fora_do_staging",
            },
        ]
    }
    assert staging.area == "Corpo"

    area_invalida = client.post(
        "/triagem/aplicar",
        json={
            "movimentos": [
                {"task_id": "staging-post", "area": "Inexistente"}
            ]
        },
    )
    assert area_invalida.status_code == 422

    staging_como_destino = client.post(
        "/triagem/aplicar",
        json={
            "movimentos": [
                {"task_id": "staging-post", "area": "Staging"}
            ]
        },
    )
    assert staging_como_destino.status_code == 422

    vazio = client.post(
        "/triagem/aplicar",
        json={"movimentos": []},
    )
    assert vazio.status_code == 422


async def test_aplicar_triagem_clickup_confere_staging(monkeypatch):
    movimentos_clickup = []
    eventos = []

    monkeypatch.setattr(tasks, "_use_clickup", lambda: True)

    async def fake_get_task(task_id):
        if task_id == "s1":
            return {
                "id": "s1",
                "list": {
                    "id": clickup_client.AREA_LISTS["Staging"],
                    "name": "Staging",
                },
            }
        return {
            "id": task_id,
            "list": {
                "id": clickup_client.AREA_LISTS["Trabalho"],
                "name": "Trabalho",
            },
        }

    async def fake_move_task(task_id, to_list_id):
        movimentos_clickup.append((task_id, to_list_id))
        return True

    def fake_log_event(evento, ref="", meta=None):
        eventos.append((evento, ref, meta))

    monkeypatch.setattr(clickup_client, "get_task", fake_get_task)
    monkeypatch.setattr(clickup_client, "move_task", fake_move_task)
    monkeypatch.setattr(store, "log_event", fake_log_event)

    resultados = await tasks.aplicar_triagem(
        [
            ("s1", "Corpo"),
            ("fora", "Finance"),
        ]
    )

    assert resultados == [
        {"task_id": "s1", "ok": True, "erro": None},
        {
            "task_id": "fora",
            "ok": False,
            "erro": "fora_do_staging",
        },
    ]
    assert movimentos_clickup == [
        ("s1", clickup_client.AREA_LISTS["Corpo"])
    ]
    assert eventos == [
        (
            "triagem_aplicada",
            "",
            {"n": 1, "erros": 1},
        )
    ]

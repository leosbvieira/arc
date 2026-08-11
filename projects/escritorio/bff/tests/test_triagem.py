from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import clickup_client, hermes_client, store, tasks, tz
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

    def fake_propostas():
        # Chegam do banco, gravadas quando a captura foi classificada. "Inexistente"
        # não deveria existir (o pipeline valida antes de gravar), mas a rota filtra
        # de novo: banco velho ou escrita por fora não vira sugestão errada na tela.
        return {"s1": "Trabalho", "s2": "Inexistente"}

    def hermes_proibido(*_args, **_kwargs):
        raise AssertionError("a triagem não pode chamar o Hermes: a proposta é lida")

    monkeypatch.setattr(tasks, "_source", fake_source)
    monkeypatch.setattr(store, "areas_propostas_por_task", fake_propostas)
    monkeypatch.setattr(hermes_client, "propose_triage", hermes_proibido)

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


async def test_item_sem_proposta_guardada_aparece_sem_sugestao(monkeypatch):
    """Entrou no Staging por fora da captura — criado à mão no ClickUp, ou é
    anterior à coluna `area_proposta`. É o caso NORMAL, não erro: aparece na
    triagem sem sugestão e o Leo escolhe. Mesmo comportamento de quando o Hermes
    estava fora do ar, só que agora sem esperar 11s para descobrir isso."""
    staging_a = tasks._Task("s1", "Primeiro", "Staging")
    staging_b = tasks._Task("s2", "Segundo", "Staging")

    async def fake_source():
        return [staging_a, staging_b], []

    monkeypatch.setattr(tasks, "_source", fake_source)
    monkeypatch.setattr(store, "areas_propostas_por_task", dict)

    pack = await tasks.triagem_pack()

    assert pack["n"] == 2
    assert [
        item["area_proposta"] for item in pack["itens"]
    ] == [None, None]


def test_get_triagem_retorna_shape_correto(client, monkeypatch):
    staging = tasks._Task("staging-get", "Captura nova", "Staging")
    monkeypatch.setattr(tasks, "_MOCK", [*tasks._MOCK, staging])

    # A proposta veio do pipeline da captura e está no banco, ligada ao id da task.
    store.enqueue_capture("comprar cueca", None, client_key="k-triagem")
    store.mark_capture(1, clickup_task_id="staging-get", area_proposta="Estudo")

    def hermes_proibido(*_args, **_kwargs):
        raise AssertionError("a rota /triagem não pode chamar o Hermes")

    monkeypatch.setattr(hermes_client, "propose_triage", hermes_proibido)

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
                "prazo": None,
            },
            {
                "task_id": "desconhecida",
                "ok": False,
                "erro": "nao_encontrado",
                "prazo": None,
            },
            {
                "task_id": "t1",
                "ok": False,
                "erro": "fora_do_staging",
                "prazo": None,
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
            ("s1", "Corpo", None),
            ("fora", "Finance", None),
        ]
    )

    assert resultados == [
        {"task_id": "s1", "ok": True, "erro": None, "prazo": None},
        {
            "task_id": "fora",
            "ok": False,
            "erro": "fora_do_staging",
            "prazo": None,
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


# ---- prazo opcional na triagem ------------------------------------------------
#
# Triar dizia só ONDE a tarefa mora. A tarefa saía do Staging, caía na área sem data
# nenhuma, e "hoje" no app se monta por data de vencimento: ela sumia do Staging e não
# aparecia em lugar que cobrasse. Triar é o momento natural de dizer QUANDO.


def _clickup_falso(monkeypatch, *, prazos, set_due_resultado=True, explode=False):
    """Staging para todo mundo, move sempre ok, e grava os set_due que chegarem."""
    monkeypatch.setattr(tasks, "_use_clickup", lambda: True)

    async def fake_get_task(task_id):
        return {
            "id": task_id,
            "list": {
                "id": clickup_client.AREA_LISTS["Staging"],
                "name": "Staging",
            },
        }

    async def fake_move_task(task_id, to_list_id):
        return True

    async def fake_set_due(task_id, due_ts, **kwargs):
        if explode:
            raise RuntimeError("clickup caiu")
        prazos.append((task_id, due_ts))
        return set_due_resultado

    monkeypatch.setattr(clickup_client, "get_task", fake_get_task)
    monkeypatch.setattr(clickup_client, "move_task", fake_move_task)
    monkeypatch.setattr(clickup_client, "set_due", fake_set_due)
    monkeypatch.setattr(store, "log_event", lambda *a, **k: None)


async def test_sem_prazo_nao_chama_o_clickup(monkeypatch):
    """`prazo: None` quer dizer "ele não pediu" — e não pode virar uma data qualquer."""
    prazos = []
    _clickup_falso(monkeypatch, prazos=prazos)

    resultados = await tasks.aplicar_triagem([("s1", "Corpo", None)])

    assert resultados == [{"task_id": "s1", "ok": True, "erro": None, "prazo": None}]
    assert prazos == []


async def test_prazo_pedido_vira_meia_noite_local(monkeypatch):
    """Mesma conversão do POST /tasks: data civil + 00:00 no fuso do Leo. Num VPS em
    UTC, usar o relógio do processo jogaria a tarefa para o dia seguinte."""
    prazos = []
    _clickup_falso(monkeypatch, prazos=prazos)

    resultados = await tasks.aplicar_triagem([("s1", "Corpo", "2026-08-11")])

    assert resultados == [{"task_id": "s1", "ok": True, "erro": None, "prazo": "ok"}]
    (task_id, due_ts) = prazos[0]
    assert task_id == "s1"
    esperado = datetime(2026, 8, 11, 0, 0, tzinfo=tz.TZ).timestamp()
    assert due_ts == esperado


async def test_prazo_que_falha_nao_desfaz_nem_esconde_o_movimento(monkeypatch):
    """O movimento não tem desfazer. Se a falha de data marcasse a tarefa como não
    movida, ele triaria de novo o que já triou — e a segunda vez daria
    `fora_do_staging`, porque a tarefa já saiu."""
    prazos = []
    _clickup_falso(monkeypatch, prazos=prazos, set_due_resultado=False)

    resultados = await tasks.aplicar_triagem([("s1", "Corpo", "2026-08-11")])

    assert resultados == [
        {"task_id": "s1", "ok": True, "erro": None, "prazo": "falhou"}
    ]


async def test_excecao_no_prazo_tambem_preserva_o_movimento(monkeypatch):
    """Não basta tratar o `False`: `set_due` faz rede e pode estourar."""
    _clickup_falso(monkeypatch, prazos=[], explode=True)

    resultados = await tasks.aplicar_triagem([("s1", "Corpo", "2026-08-11")])

    assert resultados == [
        {"task_id": "s1", "ok": True, "erro": None, "prazo": "falhou"}
    ]


def test_due_malformado_e_recusado_na_rota(client, monkeypatch):
    """Fail-closed igual ao adiar: data ambígua não vira cobrança silenciosa."""
    for ruim in ["11/08/2026", "2026-8-11", "amanhã", "2026-13-45", ""]:
        resposta = client.post(
            "/triagem/aplicar",
            json={"movimentos": [{"task_id": "t", "area": "Corpo", "due": ruim}]},
        )
        assert resposta.status_code == 422, ruim

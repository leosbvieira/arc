"""Fatia 2: terminar uma obra cria a tarefa de resumão no ClickUp.

O que muda em relação à fatia 1 é que terminar passou a ter **efeito externo**, e o
POST do ClickUp não é idempotente — diferente do vault, que escreve em path
determinístico. Daí o estado 'terminando': a obra fica reservada até se saber o que
aconteceu lá fora, e liberar sem prova é o erro caro (uma sessão nova entraria no
ciclo e o retry reconciliaria um resumão que não a contém).
"""
import pytest
from fastapi.testclient import TestClient

from app import clickup_client, resumo_obra, store, tasks
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    monkeypatch.setattr(tasks, "_MOCK", [])
    monkeypatch.setattr(tasks, "_MOCK_DESCRICOES", {})
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _sessao_compilada(book_id, *, inicial, final, compiled_at, key, vault_path=None):
    sessao, _ = store.create_reading_session(
        key, "irrelevante", pagina_inicial=inicial, inicio=1.0, book_id=book_id
    )
    with store.closing(store._connect()) as con:
        con.execute(
            "UPDATE reading_sessions SET status='compiled', pagina_final=?, "
            "compiled_at=?, vault_path=? WHERE id=?",
            (final, compiled_at, vault_path, sessao["id"]),
        )
        con.commit()
    return sessao["id"]


# ---- template -----------------------------------------------------------------


def test_os_quatro_formatos_de_pagina():
    """Iguais aos do frontmatter. Inventar o limite que falta seria escrever no
    ClickUp um número que ele nunca disse — e é o campo que diz onde ele parou."""
    assert resumo_obra.faixa_de_paginas(30, 42) == "p. 30–42"
    assert resumo_obra.faixa_de_paginas(30, None) == "a partir da p. 30"
    assert resumo_obra.faixa_de_paginas(None, 42) == "até a p. 42"
    assert resumo_obra.faixa_de_paginas(None, None) == "sem página registrada"


def test_agregado_usa_o_menor_inicio_e_o_maior_fim_registrados():
    sessoes = [
        {"pagina_inicial": 30, "pagina_final": 42},
        {"pagina_inicial": 42, "pagina_final": None},
        {"pagina_inicial": None, "pagina_final": 90},
    ]
    assert resumo_obra.agregado_de_paginas(sessoes) == "p. 30–90"


def test_agregado_de_ciclo_sem_pagina_nenhuma():
    assert resumo_obra.agregado_de_paginas(
        [{"pagina_inicial": None, "pagina_final": None}]
    ) == "sem página registrada"


def test_nome_so_cita_o_ciclo_a_partir_da_releitura():
    # "leitura 1" na primeira vez seria ruído: toda obra teria o sufixo.
    assert resumo_obra.nome("Sapiens", 1) == "Resumão: Sapiens"
    assert resumo_obra.nome("Sapiens", 2) == "Resumão: Sapiens (leitura 2)"


def test_descricao_abre_com_o_marker_e_leva_os_caminhos_do_vault():
    corpo = resumo_obra.descricao(
        titulo="Sapiens",
        book_id=7,
        ciclo=1,
        sessoes=[
            {
                "compiled_at": 1786417604.0,
                "pagina_inicial": 30,
                "pagina_final": 42,
                "vault_path": "Leituras/2026-08-10 - leitura-r11-2fc074c102.md",
            }
        ],
    )
    assert corpo.splitlines()[0] == "[book-summary:7:1]"
    # O caminho é neutro por desenho (lei 7) e é o que torna o resumão fazível
    # sem reabrir o app.
    assert "Leituras/2026-08-10 - leitura-r11-2fc074c102.md" in corpo
    assert "p. 30–42" in corpo
    assert "**A tese, em uma frase:**" in corpo


def test_descricao_nao_quebra_com_sessao_sem_data_nem_caminho():
    corpo = resumo_obra.descricao(
        titulo="Sapiens",
        book_id=1,
        ciclo=1,
        sessoes=[{"compiled_at": None, "pagina_inicial": None, "pagina_final": None}],
    )
    assert "sem data" in corpo
    assert "sem página registrada" in corpo


# ---- terminar -----------------------------------------------------------------


def test_terminar_cria_o_resumao_no_staging(client):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=30, final=42, compiled_at=10.0, key="a")

    resposta = client.post(f"/reading/books/{livro['id']}/terminar")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["book"]["status"] == "terminado"
    assert corpo["resumo_task_id"] is not None
    criada = next(t for t in tasks._MOCK if t.id == corpo["resumo_task_id"])
    assert criada.name == "Resumão: Sapiens"
    # Lei 3: vai para a triagem como qualquer captura, ele decide área e prazo.
    assert criada.area == clickup_client.STAGING


def test_ciclo_vazio_termina_sem_criar_tarefa(client):
    """Obra sem sessão nenhuma não tem o que resumir, e o caso comum é obra criada
    por engano. Criar a tarefa aqui encheria o Staging de resumão de nada."""
    livro, _ = store.create_book("Criada sem querer")

    resposta = client.post(f"/reading/books/{livro['id']}/terminar")

    assert resposta.status_code == 200
    assert resposta.json()["resumo_task_id"] is None
    assert resposta.json()["book"]["status"] == "terminado"
    assert tasks._MOCK == []


def test_falha_ao_criar_deixa_a_obra_RESERVADA(client, monkeypatch):
    """O ponto inteiro da fatia. Voltar para 'lendo' aqui seria adivinhar que nada
    foi criado — e se tiver sido, uma sessão nova entra num ciclo já resumido."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=30, final=42, compiled_at=10.0, key="a")

    async def explode(**kwargs):
        raise RuntimeError("timeout no clickup")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", explode)

    resposta = client.post(f"/reading/books/{livro['id']}/terminar")

    assert resposta.status_code == 502
    assert resposta.json()["detail"] == "book_resumao_indisponivel"
    assert store.get_book(livro["id"])["status"] == "terminando"


def test_obra_reservada_nao_aceita_sessao_nova(client, monkeypatch):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def explode(**kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", explode)
    client.post(f"/reading/books/{livro['id']}/terminar")

    with pytest.raises(store.BookIndisponivel):
        store.create_reading_session("nova", "x", inicio=2.0, book_id=livro["id"])


def test_reabrir_durante_o_fechamento_nao_mente(client, monkeypatch):
    """Na fatia 1, `rowcount != 1` virava `ja_lendo` — correto com dois estados. Com
    'terminando' no meio, essa resposta passou a ser mentira."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def explode(**kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", explode)
    client.post(f"/reading/books/{livro['id']}/terminar")

    resposta = client.post(f"/reading/books/{livro['id']}/reabrir")
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "book_terminando"


def test_terminar_de_novo_enquanto_fecha(client, monkeypatch):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def explode(**kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", explode)
    client.post(f"/reading/books/{livro['id']}/terminar")

    resposta = client.post(f"/reading/books/{livro['id']}/terminar")
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "book_terminando"


# ---- reconciliar --------------------------------------------------------------


def test_reconciliar_acha_a_tarefa_pelo_marker_e_conclui(client, monkeypatch):
    """O POST chegou no ClickUp e a resposta se perdeu: a tarefa existe, a obra está
    presa. Reconciliar adota a tarefa em vez de criar uma segunda."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def cria_e_some(**kwargs):
        # O efeito colateral acontece e a resposta se perde: é exatamente o caso que
        # torna o POST não idempotente e que a reserva existe para cobrir.
        tarefa = tasks._Task("t99", kwargs["nome"], clickup_client.STAGING)
        tasks._MOCK.append(tarefa)
        tasks._MOCK_DESCRICOES["t99"] = kwargs["descricao"]
        raise RuntimeError("resposta perdida")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", cria_e_some)
    client.post(f"/reading/books/{livro['id']}/terminar")
    assert store.get_book(livro["id"])["status"] == "terminando"

    resposta = client.post(f"/reading/books/{livro['id']}/terminar/reconciliar")

    assert resposta.status_code == 200
    assert resposta.json()["resultado"] == "terminado"
    assert resposta.json()["resumo_task_id"] == "t99"
    assert store.get_book(livro["id"])["status"] == "terminado"
    # E nenhuma tarefa a mais foi criada.
    assert len(tasks._MOCK) == 1


def test_reconciliar_com_prova_de_ausencia_devolve_para_lendo(client, monkeypatch):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def explode(**kwargs):
        raise RuntimeError("nem chegou no clickup")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", explode)
    client.post(f"/reading/books/{livro['id']}/terminar")

    resposta = client.post(f"/reading/books/{livro['id']}/terminar/reconciliar")

    assert resposta.status_code == 200
    assert resposta.json()["resultado"] == "liberado"
    assert store.get_book(livro["id"])["status"] == "lendo"


def test_busca_que_falha_nao_e_prova_de_ausencia(client, monkeypatch):
    """A distinção que segura tudo: `None` significa "procurei e não existe". Erro
    de rede significa "não sei", e não-saber tem que deixar a obra onde está."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def explode(**kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", explode)
    client.post(f"/reading/books/{livro['id']}/terminar")

    async def busca_quebrada(_marker):
        raise RuntimeError("clickup fora do ar")

    monkeypatch.setattr(tasks, "achar_resumao_de_obra", busca_quebrada)

    resposta = client.post(f"/reading/books/{livro['id']}/terminar/reconciliar")

    assert resposta.status_code == 502
    assert store.get_book(livro["id"])["status"] == "terminando"


def test_reconciliar_obra_que_nao_esta_fechando(client):
    livro, _ = store.create_book("Sapiens")
    resposta = client.post(f"/reading/books/{livro['id']}/terminar/reconciliar")
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "book_nao_esta_terminando"


# ---- listagem e ciclo ---------------------------------------------------------


def test_obra_reservada_e_listavel(client, monkeypatch):
    """Obra presa some das duas listas normais. Uma obra invisível é uma obra que
    ninguém reconcilia."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def explode(**kwargs):
        raise RuntimeError("timeout")

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", explode)
    client.post(f"/reading/books/{livro['id']}/terminar")

    assert client.get("/reading/books?status=lendo").json()["books"] == []
    assert client.get("/reading/books?status=terminado").json()["books"] == []
    presas = client.get("/reading/books?status=terminando").json()["books"]
    assert [b["id"] for b in presas] == [livro["id"]]
    assert presas[0]["terminando_desde"] is not None


def test_o_resumao_da_leitura_anterior_nao_reaparece_na_releitura(client):
    """Reabrir incrementa o ciclo. Mostrar a tarefa do ciclo 1 na leitura 2 seria a
    mesma armadilha que a página derivada já evita."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")
    client.post(f"/reading/books/{livro['id']}/terminar")

    terminados = client.get("/reading/books?status=terminado").json()["books"]
    assert terminados[0]["resumo_task_id"] is not None

    client.post(f"/reading/books/{livro['id']}/reabrir")

    lendo = client.get("/reading/books?status=lendo").json()["books"]
    assert lendo[0]["ciclo"] == 2
    assert lendo[0]["resumo_task_id"] is None


def test_fencing_recusa_conclusao_de_ciclo_que_nao_existe_mais(client):
    """Se a obra foi reaberta enquanto o POST corria, concluir com o ciclo velho
    marcaria como terminada uma leitura que recomeçou."""
    livro, _ = store.create_book("Sapiens")
    estado, reservada = store.iniciar_terminar_book(livro["id"])
    assert estado == "terminando"

    with store.closing(store._connect()) as con:
        con.execute("UPDATE books SET ciclo = 9 WHERE id = ?", (livro["id"],))
        con.commit()

    resultado, _ = store.concluir_terminar_book(livro["id"], reservada["ciclo"], "t1")
    assert resultado == "nao_reservado"
    assert store.get_book(livro["id"])["status"] == "terminando"


def test_a_segunda_leitura_gera_o_seu_proprio_resumao(client):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")
    primeira = client.post(f"/reading/books/{livro['id']}/terminar").json()

    client.post(f"/reading/books/{livro['id']}/reabrir")
    _sessao_compilada(livro["id"], inicial=1, final=20, compiled_at=20.0, key="b")
    segunda = client.post(f"/reading/books/{livro['id']}/terminar").json()

    assert segunda["resumo_task_id"] != primeira["resumo_task_id"]
    criada = next(t for t in tasks._MOCK if t.id == segunda["resumo_task_id"])
    assert criada.name == "Resumão: Sapiens (leitura 2)"
    # E o resumão da leitura 2 só fala das sessões da leitura 2.
    assert "[book-summary:%d:2]" % livro["id"] in tasks._MOCK_DESCRICOES[criada.id]


# ---- achados da revisão hostil (GPT-5.6 Sol, 11/ago) ---------------------------


async def test_marker_e_procurado_em_todas_as_listas_nao_so_no_staging(monkeypatch):
    """CRÍTICO. O resumão nasce no Staging, mas o passo seguinte natural do Leo é
    triá-lo para uma área. Se ele fizer isso antes de reconciliar, uma busca só no
    Staging concluiria "não existe", liberaria a obra, e o próximo terminar criaria
    o SEGUNDO resumão — exatamente o que a máquina de estados existe para evitar."""
    monkeypatch.setattr(tasks, "_use_clickup", lambda: True)
    consultadas = []

    async def fake_find(list_id, marker):
        consultadas.append(list_id)
        # Está em Estudo, não no Staging: ele já triou.
        return "t42" if list_id == clickup_client.AREA_LISTS["Estudo"] else None

    monkeypatch.setattr(clickup_client, "find_task_by_marker", fake_find)

    assert await tasks.achar_resumao_de_obra("[book-summary:1:1]") == "t42"
    # E o Staging vem primeiro, que é onde ela está quase sempre.
    assert consultadas[0] == clickup_client.AREA_LISTS[clickup_client.STAGING]


async def test_clickup_sem_id_e_falha_nao_ciclo_vazio(monkeypatch):
    """IMPORTANTE. `None` é o mesmo valor que significa "ciclo vazio, nada a
    resumir". Devolvê-lo numa resposta 2xx sem `id` tiraria a obra da estante com o
    app dizendo "não havia sessão para resumir" — sobre um livro que ele leu."""
    monkeypatch.setattr(tasks, "_use_clickup", lambda: True)

    async def cria_sem_id(*_args, **_kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(clickup_client, "create", cria_sem_id)

    with pytest.raises(RuntimeError, match="resumao_sem_id"):
        await tasks.criar_resumao_de_obra(nome="Resumão: x", descricao="y")


def test_reserva_perdida_no_meio_nao_vira_200(client, monkeypatch):
    """IMPORTANTE. Se a reserva se perde enquanto o POST corre, `concluir` não casa
    e a obra segue em `lendo`. Responder 200 diria que ela saiu da estante."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], inicial=1, final=10, compiled_at=10.0, key="a")

    async def cria_e_perde_a_reserva(**kwargs):
        # Simula uma reconciliação de outra aba liberando a obra no meio do POST.
        store.liberar_terminar_book(livro["id"], 1)
        return "t7"

    monkeypatch.setattr(tasks, "criar_resumao_de_obra", cria_e_perde_a_reserva)

    resposta = client.post(f"/reading/books/{livro['id']}/terminar")

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "book_reserva_perdida"
    assert store.get_book(livro["id"])["status"] == "lendo"


def test_faixa_agregada_nunca_sai_invertida():
    """MENOR. Os dois limites podem vir de sessões diferentes: uma registra só o
    final, a seguinte só o início. O agregado ingênuo diria "p. 101–100"."""
    texto = resumo_obra.agregado_de_paginas(
        [
            {"pagina_inicial": None, "pagina_final": 100},
            {"pagina_inicial": 101, "pagina_final": None},
        ]
    )
    assert "101–100" not in texto
    assert texto == "começou na p. 101 · chegou até a p. 100"

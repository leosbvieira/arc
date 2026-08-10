import pytest
from fastapi.testclient import TestClient

from app import anki, main, reading_frontmatter, store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _nova_obra(client, titulo="Sapiens"):
    resp = client.post("/reading/books", json={"titulo": titulo})
    assert resp.status_code == 200
    return resp.json()["book"]


def test_criar_obra_e_idempotente_por_slug(client):
    primeira = client.post("/reading/books", json={"titulo": "Sapiens"})
    segunda = client.post("/reading/books", json={"titulo": "sapiens "})
    assert primeira.json()["created"] is True
    assert segunda.json()["created"] is False
    assert segunda.json()["book"]["id"] == primeira.json()["book"]["id"]


def test_criar_obra_com_titulo_vazio(client):
    resp = client.post("/reading/books", json={"titulo": "   "})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "titulo_invalido"


def test_listar_estante(client):
    _nova_obra(client, "Sapiens")
    resp = client.get("/reading/books")
    assert resp.status_code == 200
    linha = resp.json()["books"][0]
    assert linha["titulo"] == "Sapiens"
    assert linha["pagina_atual"] is None
    assert linha["sessoes_n"] == 0


def test_terminar_pela_api(client):
    obra = _nova_obra(client)
    assert client.post(f"/reading/books/{obra['id']}/terminar").status_code == 200
    assert client.get("/reading/books").json()["books"] == []
    assert len(client.get("/reading/books?status=terminado").json()["books"]) == 1

    repetido = client.post(f"/reading/books/{obra['id']}/terminar")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "book_ja_terminado"


def test_reabrir_pela_api(client):
    obra = _nova_obra(client)
    client.post(f"/reading/books/{obra['id']}/terminar")
    resp = client.post(f"/reading/books/{obra['id']}/reabrir")
    assert resp.status_code == 200
    assert resp.json()["book"]["ciclo"] == 2

    repetido = client.post(f"/reading/books/{obra['id']}/reabrir")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "book_ja_lendo"


def test_endpoints_de_obra_inexistente(client):
    assert client.post("/reading/books/9999/terminar").status_code == 404
    assert client.post("/reading/books/9999/reabrir").status_code == 404


def test_terminar_com_sessao_aberta_pela_api(client):
    obra = _nova_obra(client)
    client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": obra["id"]},
    )
    resp = client.post(f"/reading/books/{obra['id']}/terminar")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "book_com_sessao_aberta"


def test_sessao_com_book_id_usa_o_titulo_canonico(client):
    obra = _nova_obra(client)
    resp = client.post(
        "/reading/sessions",
        json={
            "client_key": "s1",
            "livro": "TÍTULO MENTIROSO",
            "pagina_inicial": 10,
            "inicio": 1_000.0,
            "book_id": obra["id"],
        },
    )
    assert resp.status_code == 200
    sessao = resp.json()["session"]
    assert sessao["livro"] == "Sapiens"
    assert sessao["book_id"] == obra["id"]
    assert sessao["book_ciclo"] == 1


def test_sessao_com_book_id_inexistente_da_422(client):
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": 9999},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "book_nao_encontrado"


def test_sessao_em_obra_terminada_da_409(client):
    obra = _nova_obra(client)
    client.post(f"/reading/books/{obra['id']}/terminar")
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": obra["id"]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "book_nao_aceita_sessao"


def test_sessao_sem_book_id_segue_o_caminho_antigo(client):
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "Livro solto", "inicio": 1.0},
    )
    assert resp.status_code == 200
    assert resp.json()["session"]["book_id"] is None


def _sessao_com_buffer(client, obra_id=None):
    corpo = {"client_key": "s1", "livro": "Sapiens", "pagina_inicial": 190, "inicio": 1.0}
    if obra_id is not None:
        corpo["book_id"] = obra_id
    sid = client.post("/reading/sessions", json=corpo).json()["session"]["id"]
    client.post(
        f"/reading/sessions/{sid}/buffer",
        json={"seq": 1, "hook": "comentario", "texto": "um comentário", "ts": 2.0},
    )
    return sid


def test_draft_prefixa_o_frontmatter_antes_do_staging(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)

    resp = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert resp.status_code == 200
    draft = resp.json()["draft_md"]
    assert draft.startswith("---\n")
    assert 'livro: "Sapiens"' in draft
    assert "paginas: 190-214" in draft
    assert draft.endswith("# Nota do Hermes")
    # Pin nos bytes inteiros (inicio=1.0 torna a data determinística): garante que
    # nada foi injetado entre o frontmatter e o corpo, nem um dos dois duplicado.
    assert draft == reading_frontmatter.frontmatter(
        livro="Sapiens", pagina_inicial=190, pagina_final=214, inicio=1.0
    ) + "# Nota do Hermes"
    # O que ficou staged é o documento COMPLETO: é ele que o Leo aprova.
    assert store.get_reading_session(sid)["draft_md"] == draft
    assert store.get_reading_session(sid)["draft_fmt"] == 2


def test_compile_recusa_draft_legado(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})

    # Simula o preview que já estava aberto no celular quando o deploy subiu.
    with store.closing(store._connect()) as con:
        con.execute("UPDATE reading_sessions SET draft_fmt = NULL WHERE id = ?", (sid,))
        con.commit()

    async def nunca(*_a, **_k):
        raise AssertionError("o vault não pode ser tocado com draft legado")

    monkeypatch.setattr(main.vault_client, "write_reading_note", nunca)

    resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 214, "fim": 100.0, "duracao_s": 60},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "reading_draft_desatualizado"
    assert store.get_reading_session(sid)["status"] == "pending"


def test_draft_legado_e_regenerado_e_nao_reusado(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])
    chamadas = {"n": 0}

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        chamadas["n"] += 1
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 1

    # Mesmo digest, mas formato antigo: tem que regenerar.
    with store.closing(store._connect()) as con:
        con.execute("UPDATE reading_sessions SET draft_fmt = NULL WHERE id = ?", (sid,))
        con.commit()
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 2

    # Formato atual e mesmo digest: reusa, sem chamar o Hermes de novo.
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 2


def test_deck_para_livro():
    assert anki.deck_para_livro("Sapiens") == "Leitura::Sapiens"
    # `::` é o separador de subdeck do Anki: um título que o contenha criaria uma
    # árvore acidental.
    assert anki.deck_para_livro("A::B") == "Leitura::A-B"
    assert anki.deck_para_livro("  espaços  demais ") == "Leitura::espaços demais"
    assert anki.deck_para_livro("   ") == ""


def test_card_nasce_no_deck_da_obra(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota"

    async def suggest_anki(notas):
        # O modelo TENTA escolher o deck. O valor dele não pode valer.
        return [
            {
                "frente": "f",
                "meaning": "m",
                "example": "e",
                "hook": "h",
                "deck": "DeckDoModelo",
            }
        ]

    async def write_reading_note(*_a, **_k):
        return "Leituras/x.md"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading_note)

    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 214, "fim": 100.0, "duracao_s": 60},
    )
    assert resp.status_code == 200
    cards = resp.json()["anki_cards"]
    assert cards[0]["deck"] == "Leitura::Sapiens"


def test_card_de_sessao_sem_obra_fica_sem_deck(client, monkeypatch):
    sid = _sessao_com_buffer(client)

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota"

    async def suggest_anki(notas):
        return [{"frente": "f", "meaning": "m", "example": "e", "hook": "h"}]

    async def write_reading_note(*_a, **_k):
        return "Leituras/x.md"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading_note)

    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 214, "fim": 100.0, "duracao_s": 60},
    )
    assert resp.json()["anki_cards"][0]["deck"] == ""


def test_anki_sugerir_sem_session_id_nao_quebra(client, monkeypatch):
    async def suggest_anki(notas):
        return [{"frente": "f", "meaning": "m", "example": "e", "hook": "h"}]

    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)
    resp = client.post("/anki/sugerir", json={"notas": "algum texto"})
    assert resp.status_code == 200
    assert resp.json()["cards"][0]["deck"] == ""


def test_tsv_carrega_o_deck_por_linha():
    linhas = anki.tsv(
        [
            {"frente": "a", "meaning": "b", "example": "c", "hook": "d",
             "deck": "Leitura::Sapiens"},
            {"frente": "e", "meaning": "f", "example": "g", "hook": "h", "deck": ""},
        ]
    )
    corpo = [l for l in linhas.splitlines() if not l.startswith("#")]
    assert corpo[0].split("\t")[4] == "Leitura::Sapiens"
    # Card antigo, sem obra: cai no deck-pai. O TSV NUNCA emite célula vazia —
    # é o que dispensa saber o que o Anki faria com ela.
    assert corpo[1].split("\t") == ["e", "f", "g", "h", "Leitura"]
    assert linhas.startswith("#separator:tab\n")


def test_tsv_nunca_emite_celula_de_deck_vazia():
    for card in ({"frente": "a"}, {"frente": "a", "deck": None}, {"frente": "a", "deck": "  "}):
        corpo = [l for l in anki.tsv([card]).splitlines() if not l.startswith("#")]
        assert corpo[0].split("\t")[4] == "Leitura"


def test_anki_sugerir_resolve_deck_pela_sessao_compilada_certa(client, monkeypatch):
    # `sessions.id` e `reading_sessions.id` são AUTOINCREMENT independentes: o
    # mesmo número pode nomear linhas de obras diferentes. Esta armadilha força a
    # colisão para provar que /anki/sugerir busca a sessão de leitura que RESULTOU
    # na compilação (via compiled_session_id), não a que só tem o id parecido.
    obra_b = _nova_obra(client, "Livro B")
    armadilha = client.post(
        "/reading/sessions",
        json={"client_key": "decoy", "livro": "Livro B", "inicio": 1.0, "book_id": obra_b["id"]},
    ).json()["session"]["id"]

    obra_a = _nova_obra(client, "Livro A")
    sid = client.post(
        "/reading/sessions",
        json={
            "client_key": "alvo",
            "livro": "Livro A",
            "pagina_inicial": 1,
            "inicio": 1.0,
            "book_id": obra_a["id"],
        },
    ).json()["session"]["id"]
    client.post(
        f"/reading/sessions/{sid}/buffer",
        json={"seq": 1, "hook": "comentario", "texto": "nota", "ts": 2.0},
    )

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota"

    async def write_reading_note(*_a, **_k):
        return "Leituras/x.md"

    async def suggest_anki_falha(notas):
        # Faz o compile terminar SEM consumir a sugestão automática, para poder
        # chamar /anki/sugerir manualmente depois e observar a resolução de deck.
        raise RuntimeError("boom")

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading_note)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki_falha)

    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 10})
    compile_resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 10, "fim": 100.0, "duracao_s": 60},
    )
    assert compile_resp.status_code == 200
    assert compile_resp.json()["anki_status"] == "pending"
    compiled_session_id = compile_resp.json()["session"]["compiled_session_id"]
    # A armadilha só prova algo se os ids realmente colidirem.
    assert compiled_session_id == armadilha

    async def suggest_anki_ok(notas):
        return [{"frente": "f", "meaning": "m", "example": "e", "hook": "h"}]

    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki_ok)

    resp = client.post(
        "/anki/sugerir",
        json={"notas": "algum texto", "session_id": compiled_session_id},
    )
    assert resp.status_code == 200
    assert resp.json()["cards"][0]["deck"] == "Leitura::Livro A"

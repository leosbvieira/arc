"""Fatia 3: onde a leitura parou, escrito no fim de uma sessão para a próxima achar.

Ele pediu isto na conversa que originou a estante: *"ao começar uma sessão, eu quero o
resumo do hermes. Porém ele não precisa ser ao começar a sessão, pode ser ao finalizar a
sessão anterior. E aí quando eu começar uma nova, já está lá."*

Duas propriedades sustentam o desenho e são o que estes testes protegem:

1. **As citações não entram no payload do modelo.** `compile_reading` as insere por
   código, fora do que o Hermes vê. Gerar o recap a partir da nota pronta desfaria esse
   isolamento, porque a nota já tem as citações coladas no fim.
2. **Best-effort e não regenerável.** O buffer é purgado no compile; falhou uma vez,
   aquela sessão fica sem recap para sempre. Então falhar não pode derrubar o compile —
   a nota já está no vault quando o recap é tentado.
"""
import pytest
from fastapi.testclient import TestClient

from app import hermes_client, store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    return None


@pytest.fixture
def client(db, monkeypatch):
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _chunk(seq, hook, texto):
    return {"seq": seq, "hook": hook, "texto": texto}


# ---- o payload do modelo ------------------------------------------------------


async def test_citacao_nao_entra_no_payload_do_recap(monkeypatch):
    """O mesmo isolamento da nota. Uma citação é texto do autor, não raciocínio dele —
    e o desenho inteiro depende de o modelo nunca reescrevê-la."""
    monkeypatch.setattr(settings, "hermes_mock", False)
    prompts = []

    async def fake_oneshot(prompt, **_kw):
        prompts.append(prompt)
        return "Você parou na discussão sobre ordem imaginada."

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    await hermes_client.recap_reading(
        "Sapiens",
        [
            _chunk(1, "comentario", "a tese é que a ficção compartilhada escala"),
            _chunk(2, "quote", "TEXTO LITERAL DO LIVRO QUE NAO PODE VAZAR"),
        ],
    )

    assert "ficção compartilhada" in prompts[0]
    assert "TEXTO LITERAL DO LIVRO QUE NAO PODE VAZAR" not in prompts[0]


async def test_sessao_so_de_citacao_nao_chama_o_modelo(monkeypatch):
    """Sem comentário não há raciocínio para retomar, e pagar uma chamada de LLM para
    devolver nada é desperdício com latência."""
    monkeypatch.setattr(settings, "hermes_mock", False)

    async def proibido(_prompt):
        raise AssertionError("não devia chamar o Hermes")

    monkeypatch.setattr(hermes_client, "_oneshot", proibido)

    assert await hermes_client.recap_reading("Sapiens", [_chunk(1, "quote", "x")]) == ""


async def test_recap_vira_uma_linha_e_tem_teto(monkeypatch):
    """O recap ocupa a linha da estante. Um modelo que resolve escrever uma página não
    pode empurrar a lista inteira para fora da tela."""
    monkeypatch.setattr(settings, "hermes_mock", False)

    async def fake_oneshot(_prompt, **_kw):
        return "linha um\n\n  linha dois  \n" + ("x" * 900)

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    recap = await hermes_client.recap_reading("Sapiens", [_chunk(1, "comentario", "a")])

    assert "\n" not in recap
    assert recap.startswith("linha um linha dois ")
    assert len(recap) == hermes_client.RECAP_MAX_CHARS


# ---- o recap no ciclo de vida da sessão ---------------------------------------


def _sessao_compilada(book_id, *, compiled_at, key, recap=None, pagina_final=None):
    sessao, _ = store.create_reading_session(
        key, "irrelevante", pagina_inicial=1, inicio=1.0, book_id=book_id
    )
    with store.closing(store._connect()) as con:
        con.execute(
            "UPDATE reading_sessions SET status='compiled', compiled_at=?, "
            "recap=?, pagina_final=? WHERE id=?",
            (compiled_at, recap, pagina_final, sessao["id"]),
        )
        con.commit()
    return sessao["id"]


def test_a_estante_mostra_o_recap_da_ultima_sessao(db):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], compiled_at=10.0, key="a", recap="parou no capítulo 2")
    _sessao_compilada(livro["id"], compiled_at=20.0, key="b", recap="parou no capítulo 5")

    assert store.list_books("lendo")[0]["recap"] == "parou no capítulo 5"


def test_sessao_sem_recap_NAO_herda_o_da_anterior(db):
    """Regra deliberadamente OPOSTA à da página, e a revisão hostil é que apontou.

    Página é fato que envelhece bem: "p. 42" segue sendo a última página conhecida.
    Recap é afirmação sobre onde ele parou — se a última sessão foi até o capítulo 8
    e o Hermes falhou nela, exibir "você parou no capítulo 2" da sessão anterior é
    dizer algo falso na tela. Silêncio é melhor que lembrete errado.
    """
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], compiled_at=10.0, key="a", recap="parou no capítulo 2")
    _sessao_compilada(livro["id"], compiled_at=20.0, key="b", recap=None)

    assert store.list_books("lendo")[0]["recap"] is None
    # E a página, que segue a regra contrária, continua vindo da sessão que a tem.
    assert store.list_books("lendo")[0]["pagina_atual"] is None


def test_recap_vazio_tambem_nao_ressuscita_o_anterior(db):
    """String vazia é o que sobra quando o modelo devolve nada. A normalização de
    ""→null é da tela (`shelfView`), não do banco: aqui só importa que o recap velho
    não volte."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], compiled_at=10.0, key="a", recap="parou no capítulo 2")
    _sessao_compilada(livro["id"], compiled_at=20.0, key="b", recap="")

    assert not store.list_books("lendo")[0]["recap"]


def test_o_recap_da_leitura_anterior_nao_vaza_para_a_releitura(db):
    """Reabrir recomeça a obra. Dizer "você parou no capítulo 5" para quem está na
    página 1 da segunda leitura é a mesma armadilha da página derivada."""
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], compiled_at=10.0, key="a", recap="parou no capítulo 5")
    estado, obra = store.iniciar_terminar_book(livro["id"])
    store.concluir_terminar_book(livro["id"], obra["ciclo"], None)
    store.reabrir_book(livro["id"])

    assert store.list_books("lendo")[0]["recap"] is None


def test_o_recap_ve_o_buffer_da_sessao_e_fica_gravado(client, monkeypatch):
    """O recap nasce do buffer da sessão, e termina visível na estante.

    A chamada usa o `session["buffer"]` já carregado, então ela não depende de o
    purge ainda não ter rodado — mas se alguém trocar a fonte por uma releitura do
    banco, este teste é o que pega o buffer vazio.
    """
    monkeypatch.setattr(settings, "hermes_mock", True)
    livro, _ = store.create_book("Sapiens")
    sessao, _ = store.create_reading_session(
        "k", "Sapiens", pagina_inicial=1, inicio=1.0, book_id=livro["id"]
    )
    sid = sessao["id"]
    client.post(f"/reading/sessions/{sid}/buffer", json={
        "seq": 1, "hook": "comentario", "texto": "a tese é que a ficção escala", "ts": 1.0,
    })

    vistos = []

    async def fake_recap(livro_nome, chunks):
        vistos.append(len(chunks))
        return "você parou na tese da ficção compartilhada"

    monkeypatch.setattr(hermes_client, "recap_reading", fake_recap)

    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 10})

    import app.main as main

    async def fake_write(*_args, **_kwargs):
        return "Leituras/nota.md"

    monkeypatch.setattr(main.vault_client, "write_reading_note", fake_write)

    resposta = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 10, "fim": 2.0, "duracao_s": 60},
    )

    assert resposta.status_code == 200
    assert vistos == [1], "o recap tem que ver o buffer, não o buffer já purgado"
    assert store.list_books("lendo")[0]["recap"] == "você parou na tese da ficção compartilhada"


def test_falha_do_recap_nao_derruba_o_compile(client, monkeypatch):
    """A nota já está no vault quando o recap é tentado. Estourar aqui devolveria 502
    para uma publicação que deu certo, e ele tentaria de novo o que já aconteceu."""
    monkeypatch.setattr(settings, "hermes_mock", True)
    livro, _ = store.create_book("Sapiens")
    sessao, _ = store.create_reading_session(
        "k", "Sapiens", pagina_inicial=1, inicio=1.0, book_id=livro["id"]
    )
    sid = sessao["id"]
    client.post(f"/reading/sessions/{sid}/buffer", json={
        "seq": 1, "hook": "comentario", "texto": "algo", "ts": 1.0,
    })

    async def recap_quebrado(*_args, **_kwargs):
        raise RuntimeError("hermes fora do ar")

    import app.main as main

    async def fake_write(*_args, **_kwargs):
        return "Leituras/nota.md"

    monkeypatch.setattr(hermes_client, "recap_reading", recap_quebrado)
    monkeypatch.setattr(main.vault_client, "write_reading_note", fake_write)

    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 10})
    resposta = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 10, "fim": 2.0, "duracao_s": 60},
    )

    assert resposta.status_code == 200
    assert resposta.json()["session"]["status"] == "compiled"
    assert store.list_books("lendo")[0]["recap"] is None

import pytest

from app import store
from app.config import settings


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    return None


def test_slug_normaliza_caixa_acento_e_espaco(db):
    assert store.slug_livro("Sapiens") == store.slug_livro("sapiens ")
    assert store.slug_livro("Antifrágil") == store.slug_livro("ANTIFRAGIL")
    assert store.slug_livro("  dois   espaços  ") == "dois espacos"


def test_slug_preserva_pontuacao(db):
    # Descartar pontuação colapsaria estas três obras numa só.
    slugs = {store.slug_livro("C"), store.slug_livro("C++"), store.slug_livro("C#")}
    assert len(slugs) == 3


def test_slug_vazio_e_recusado(db):
    for titulo in ("", "   ", "\n\t", "\x00"):
        with pytest.raises(ValueError, match="titulo_invalido"):
            store.create_book(titulo)


def test_create_book_reusa_a_obra_de_mesmo_slug(db):
    primeira, criada = store.create_book("Sapiens")
    assert criada is True
    assert primeira["status"] == "lendo"
    assert primeira["ciclo"] == 1

    segunda, criada_de_novo = store.create_book("sapiens ")
    assert criada_de_novo is False
    assert segunda["id"] == primeira["id"]
    # O título guardado é o da primeira criação; a segunda não reescreve.
    assert segunda["titulo"] == "Sapiens"


def test_get_book(db):
    criada, _ = store.create_book("Antifrágil")
    assert store.get_book(criada["id"])["titulo"] == "Antifrágil"
    assert store.get_book(9999) is None


def test_migracao_e_idempotente(db):
    store.init_db()
    store.init_db()
    criada, _ = store.create_book("Sapiens")
    assert criada["id"] > 0


def _sessao_compilada(book_id, *, pagina_final, compiled_at, fim, key):
    """Grava direto na store o estado que /compile deixaria, para testar a derivada
    sem subir o pipeline inteiro de leitura.

    Não recebe o ciclo: quem o define é `create_reading_session`, copiando de
    `books.ciclo`. Passá-lo aqui esconderia justamente o que se quer testar.
    """
    sessao, _ = store.create_reading_session(
        key, "irrelevante", pagina_inicial=1, inicio=1.0, book_id=book_id
    )
    with store.closing(store._connect()) as con:
        con.execute(
            "UPDATE reading_sessions SET status='compiled', pagina_final=?, "
            "compiled_at=?, fim=? WHERE id=?",
            (pagina_final, compiled_at, fim, sessao["id"]),
        )
        con.commit()
    return sessao["id"]


def test_pagina_atual_e_da_sessao_compilada_mais_recente(db):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=100, compiled_at=10.0, fim=10.0, key="a")
    _sessao_compilada(livro["id"], pagina_final=214, compiled_at=20.0, fim=20.0, key="b")

    estante = store.list_books("lendo")
    assert estante[0]["pagina_atual"] == 214
    assert estante[0]["sessoes_n"] == 2
    assert estante[0]["ultima_sessao"] == 20.0


def test_pagina_atual_ignora_o_relogio_do_celular(db):
    # A segunda sessão foi compilada depois (compiled_at maior) mas mandou um `fim`
    # atrasado. Ordenar por `fim` apontaria a página errada.
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=100, compiled_at=10.0, fim=999.0, key="a")
    _sessao_compilada(livro["id"], pagina_final=214, compiled_at=20.0, fim=5.0, key="b")

    assert store.list_books("lendo")[0]["pagina_atual"] == 214


def test_sessao_recente_sem_pagina_final_nao_apaga_o_progresso(db):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=214, compiled_at=10.0, fim=10.0, key="a")
    _sessao_compilada(livro["id"], pagina_final=None, compiled_at=20.0, fim=20.0, key="b")

    assert store.list_books("lendo")[0]["pagina_atual"] == 214


def test_obra_sem_sessao_compilada(db):
    store.create_book("Recém-criada")
    linha = store.list_books("lendo")[0]
    assert linha["pagina_atual"] is None
    assert linha["ultima_sessao"] is None
    assert linha["sessoes_n"] == 0


def test_derivadas_ignoram_sessao_pendente(db):
    livro, _ = store.create_book("Sapiens")
    store.create_reading_session("p", "Sapiens", inicio=1.0, book_id=livro["id"])
    assert store.list_books("lendo")[0]["sessoes_n"] == 0

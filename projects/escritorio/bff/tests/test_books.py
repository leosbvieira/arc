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


def _terminar(book_id: int, task_id: str | None = None) -> tuple[str, dict | None]:
    """As duas fases da fatia 2 no gesto único que a fatia 1 tinha.

    Existe para os testes de CICLO seguirem falando de ciclo. Quem exercita a
    reserva, o fencing e o resumão em si é `test_resumao_de_obra.py`.
    """
    estado, obra = store.iniciar_terminar_book(book_id)
    if estado != "terminando":
        return estado, obra
    return store.concluir_terminar_book(book_id, obra["ciclo"], task_id)


def test_terminar_e_reabrir_abrem_ciclo_novo(db):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=300, compiled_at=10.0, fim=10.0, key="a")

    estado, obra = _terminar(livro["id"])
    assert estado == "terminado" and obra["status"] == "terminado"
    assert store.list_books("lendo") == []
    assert store.list_books("terminado")[0]["id"] == livro["id"]

    estado, obra = store.reabrir_book(livro["id"])
    assert estado == "reaberto" and obra["ciclo"] == 2

    # A releitura recomeça: a página do ciclo 1 não vaza para o ciclo 2.
    assert store.list_books("lendo")[0]["pagina_atual"] is None
    _sessao_compilada(livro["id"], pagina_final=120, compiled_at=30.0, fim=30.0, key="b")
    assert store.list_books("lendo")[0]["pagina_atual"] == 120


def test_terminar_duas_vezes(db):
    livro, _ = store.create_book("Sapiens")
    assert _terminar(livro["id"])[0] == "terminado"
    assert _terminar(livro["id"])[0] == "ja_terminado"


def test_terminar_com_sessao_aberta_e_recusado(db):
    livro, _ = store.create_book("Sapiens")
    sessao, _ = store.create_reading_session(
        "aberta", "x", inicio=1.0, book_id=livro["id"]
    )
    estado, detalhe = _terminar(livro["id"])
    assert estado == "sessao_aberta"
    assert detalhe["sessions"] == [sessao["id"]]
    assert store.get_book(livro["id"])["status"] == "lendo"


def test_terminar_obra_sem_sessao_funciona(db):
    # É assim que se tira da estante uma obra criada por engano.
    livro, _ = store.create_book("Criada sem querer")
    assert _terminar(livro["id"])[0] == "terminado"


def test_reabrir_obra_que_ja_esta_lendo(db):
    livro, _ = store.create_book("Sapiens")
    assert store.reabrir_book(livro["id"])[0] == "ja_lendo"
    assert store.get_book(livro["id"])["ciclo"] == 1


def test_estados_de_obra_inexistente(db):
    assert store.iniciar_terminar_book(9999)[0] == "missing"
    assert store.reabrir_book(9999)[0] == "missing"


def test_sessao_usa_o_titulo_canonico_e_o_ciclo_da_obra(db):
    livro, _ = store.create_book("Sapiens")
    sessao, _ = store.create_reading_session(
        "s1", "TÍTULO MENTIROSO", inicio=1.0, book_id=livro["id"]
    )
    assert sessao["livro"] == "Sapiens"
    assert sessao["book_id"] == livro["id"]
    assert sessao["book_ciclo"] == 1


def test_sessao_em_obra_terminada_e_recusada(db):
    livro, _ = store.create_book("Sapiens")
    _terminar(livro["id"])
    with pytest.raises(store.BookIndisponivel):
        store.create_reading_session("s1", "x", inicio=1.0, book_id=livro["id"])
    assert store.get_reading_session(1) is None


def test_sessao_com_book_id_inexistente(db):
    with pytest.raises(ValueError, match="book_nao_encontrado"):
        store.create_reading_session("s1", "x", inicio=1.0, book_id=9999)
    assert store.get_reading_session(1) is None


def test_retry_da_mesma_client_key_nao_troca_a_obra(db):
    primeira, _ = store.create_book("Sapiens")
    segunda, _ = store.create_book("Antifrágil")
    store.create_reading_session("s1", "x", inicio=1.0, book_id=primeira["id"])

    sessao, criada = store.create_reading_session(
        "s1", "x", inicio=1.0, book_id=segunda["id"]
    )
    assert criada is False
    assert sessao["book_id"] == primeira["id"]


def test_sessao_sem_book_id_segue_o_caminho_antigo(db):
    sessao, _ = store.create_reading_session("s1", "Livro solto", inicio=1.0)
    assert sessao["livro"] == "Livro solto"
    assert sessao["book_id"] is None
    assert sessao["book_ciclo"] is None

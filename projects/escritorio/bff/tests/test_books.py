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

"""O banco não pode depender de onde o servidor foi iniciado.

`DB_PATH=data.db` no `.env` é relativo, e `sqlite3.connect` resolve contra o cwd.
Subir o BFF de `projects/escritorio/` em vez de `projects/escritorio/bff/` cria um
banco NOVO e VAZIO em silêncio — sem erro, sem aviso: pontos, rotinas, capturas e
histórico simplesmente somem da tela e voltam quando você inicia do lugar certo.

Aconteceu de verdade: existe um `projects/escritorio/data.db` de 05/07 com zero
linhas, ao lado do `bff/data.db` que tem o histórico inteiro.

O default do `config.py` já era absoluto — o furo é o override do `.env`.
"""
from pathlib import Path

from app.config import Settings, _PROJECT_DIR, settings


def test_caminho_relativo_e_ancorado_no_projeto():
    config = Settings(db_path="data.db")

    assert Path(config.db_path).is_absolute()
    assert Path(config.db_path) == _PROJECT_DIR / "data.db"


def test_subpasta_relativa_tambem_e_ancorada():
    config = Settings(db_path="backups/ontem.db")

    assert Path(config.db_path) == _PROJECT_DIR / "backups" / "ontem.db"


def test_caminho_absoluto_passa_intacto(tmp_path):
    """Os testes injetam caminhos absolutos de tmp — âncora nenhuma pode mexer neles."""
    alvo = tmp_path / "t.db"

    config = Settings(db_path=str(alvo))

    assert Path(config.db_path) == alvo


def test_config_real_do_projeto_e_absoluta():
    """A guarda que importa: o `.env` do Leo não pode mais entregar caminho relativo."""
    assert Path(settings.db_path).is_absolute()


# --- lei 7 dentro da ferramenta de teste ---------------------------------------
#
# Descoberto do jeito ruim: um assert do pytest que mencionava `settings` fez o
# pydantic imprimir o objeto inteiro, e senha do app, JWT secret e internal token
# saíram em texto claro no terminal. Qualquer traceback que toque em `settings`
# — erro 500 com locals, log de debug, CI — era o mesmo vazamento.


def test_repr_nao_despeja_segredo():
    config = Settings(
        app_password="senha-de-verdade",
        jwt_secret="segredo-de-verdade",
        github_pat="ghp_naoDeveAparecer",
        clickup_token="pk_naoDeveAparecer",
        telegram_bot_token="123:naoDeveAparecer",
        internal_token="tok_naoDeveAparecer",
    )

    texto = repr(config)

    for vazamento in (
        "senha-de-verdade",
        "segredo-de-verdade",
        "ghp_naoDeveAparecer",
        "pk_naoDeveAparecer",
        "123:naoDeveAparecer",
        "tok_naoDeveAparecer",
    ):
        assert vazamento not in texto, f"vazou no repr: {vazamento}"
    assert "<oculto>" in texto


def test_repr_ainda_mostra_o_que_nao_e_segredo():
    """Ocultar tudo tornaria o repr inútil para depurar."""
    texto = repr(Settings(db_path="/tmp/x.db", hermes_mock=True, jwt_ttl_hours=42))

    assert "42" in texto
    assert "hermes_mock=True" in texto

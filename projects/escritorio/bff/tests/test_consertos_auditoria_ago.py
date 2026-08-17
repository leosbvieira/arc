"""Consertos da auditoria de 16/ago. Um teste por defeito, nomeado pelo defeito.

Cada um destes falha no código de antes — é o que os torna prova, e não decoração.
"""
import pytest
from fastapi.testclient import TestClient

from app import clickup_client, main, store, tasks, vault_client
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "app_password", "senha-de-teste")
    monkeypatch.setattr(settings, "internal_token", "itok")
    store.init_db()
    main._login_erros = []
    return TestClient(app)


def token(client) -> dict:
    r = client.post("/auth/login", json={"password": "senha-de-teste"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- /auth/login: sem limite de taxa e sem NENHUM rastro ---------------------


def test_senha_errada_deixa_rastro(client):
    # No código de antes, uma tentativa errada não escrevia em lugar nenhum: não havia
    # como saber, depois, que alguém tentou.
    client.post("/auth/login", json={"password": "chute"})
    with store._connect() as con:
        eventos = [
            r["evento"]
            for r in con.execute("SELECT evento FROM telemetry").fetchall()
        ]
    assert "login_falhou" in eventos


def test_login_bloqueia_depois_de_cinco_erros(client):
    for _ in range(main._LOGIN_MAX_ERROS):
        assert client.post("/auth/login", json={"password": "chute"}).status_code == 401
    r = client.post("/auth/login", json={"password": "chute"})
    assert r.status_code == 429
    # E o bloqueio vale mesmo pra senha CERTA — senão o atacante só precisa acertar
    # depois de errar, que é exatamente o que o limite existe pra impedir.
    assert client.post("/auth/login", json={"password": "senha-de-teste"}).status_code == 429


def test_acerto_limpa_o_contador(client):
    for _ in range(3):
        client.post("/auth/login", json={"password": "chute"})
    assert client.post("/auth/login", json={"password": "senha-de-teste"}).status_code == 200
    assert main._login_erros == []


# --- /closing/approve: o vault vinha antes do local -------------------------


def test_falha_do_vault_nao_apaga_o_fechamento_do_dia(client, monkeypatch):
    """O rito das 21h é o único que o Leo completa. Perdê-lo inteiro porque o GitHub
    piscou era o pior negócio do sistema: nem rotina, nem ponto, nem fila de retry."""
    hdr = token(client)

    async def vault_caiu(*_a, **_kw):
        raise vault_client.VaultError("vault_indisponivel")

    monkeypatch.setattr(vault_client, "write_raw", vault_caiu)

    body = {
        "template": "yoga",
        "draft_md": "fechei o dia",
        "raw_text": "despejo",
        "checks": [{"rotina": "pesagem", "feito": True}],
    }
    with pytest.raises(vault_client.VaultError):
        client.post("/closing/approve", json=body, headers=hdr)

    # O vault falhou — e MESMO ASSIM a rotina e o ponto ficaram registrados.
    from app import pontos

    hoje = pontos.hoje_local().isoformat()
    assert store.get_checks_on(hoje).get("pesagem") is True
    with store._connect() as con:
        eventos = [
            r["evento"] for r in con.execute("SELECT evento FROM telemetry").fetchall()
        ]
    assert "closing_approved" in eventos


def test_refechar_o_dia_nao_escreve_um_segundo_bloco(client, monkeypatch):
    """O marker levava o sha1 do texto, então editar o despejo e fechar de novo
    produzia marker novo e um SEGUNDO '## Fechamento' na mesma Daily."""
    hdr = token(client)
    appends: list[tuple[str, str]] = []

    async def raw(*_a, **_kw):
        return "1- Inbox/Raw/x.md"

    async def append(path, block, _msg, header_if_new="", dedupe_marker=None):
        appends.append((path, dedupe_marker))
        return path

    monkeypatch.setattr(vault_client, "write_raw", raw)
    monkeypatch.setattr(vault_client, "append_file", append)

    base = {"template": "yoga", "raw_text": "despejo", "checks": []}
    client.post("/closing/approve", json={**base, "draft_md": "primeira versão"}, headers=hdr)
    client.post("/closing/approve", json={**base, "draft_md": "TEXTO EDITADO"}, headers=hdr)

    assert len(appends) == 2
    # A dedupe do append_file é por marker: se os dois forem iguais, o segundo é no-op
    # no vault. Antes eles diferiam, e o segundo bloco entrava.
    assert appends[0][1] == appends[1][1]
    assert "fechamento:" in appends[0][1]


# --- find_task_by_marker: `None` tinha que ser prova de ausência -------------


async def test_marker_achado_sem_id_estoura_em_vez_de_virar_ausencia(monkeypatch):
    """`None` faz o caller LIBERAR a obra. Achar o marker e não conseguir nomear a
    tarefa não é ausência — devolver None ali criava o segundo resumão que toda a
    máquina de fencing existe pra impedir."""

    async def lista(*_a, **_kw):
        return [{"description": "resumo [book-summary:7:2]", "id": None}]

    monkeypatch.setattr(clickup_client, "_list_tasks", lista)
    with pytest.raises(clickup_client.MarcadorSemId):
        await clickup_client.find_task_by_marker("901327803429", "[book-summary:7:2]")


async def test_ausencia_de_verdade_continua_sendo_none(monkeypatch):
    async def lista(*_a, **_kw):
        return [{"description": "outra coisa", "id": "abc"}]

    monkeypatch.setattr(clickup_client, "_list_tasks", lista)
    assert await clickup_client.find_task_by_marker("901327803429", "[book-summary:7:2]") is None


async def test_a_busca_do_marker_cobre_arquivadas_e_subtarefas(monkeypatch):
    """Um resumão arquivado, ou triado pra debaixo de outra tarefa, lia como ausente."""
    chamadas: list[dict] = []

    async def lista(_client, _list_id, **kwargs):
        chamadas.append(kwargs)
        return []

    monkeypatch.setattr(clickup_client, "_list_tasks", lista)
    await clickup_client.find_task_by_marker("901327803429", "[book-summary:7:2]")

    assert [c["archived"] for c in chamadas] == [False, True], "varre as duas metades"
    assert all(c["subtasks"] for c in chamadas)
    assert all(c["include_closed"] for c in chamadas)


# --- /abertura: uma falha do ClickUp apagava o pack local inteiro ------------


def test_clickup_fora_do_ar_nao_derruba_a_abertura(client, monkeypatch):
    async def clickup_caiu():
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr(tasks, "due_hoje", clickup_caiu)
    r = client.get("/abertura", headers=token(client))

    assert r.status_code == 200, "o pack da manhã é SQLite local; não depende do ClickUp"
    corpo = r.json()
    assert corpo["hoje"]["tarefas_due"] == []
    # E diz que não sabe, em vez de fingir que não há tarefa nenhuma.
    assert corpo["hoje"]["tarefas_indisponivel"] is True
    assert "rotinas_manha" in corpo and "template" in corpo


def test_abertura_normal_nao_marca_indisponivel(client, monkeypatch):
    async def sem_tarefas():
        return []

    monkeypatch.setattr(tasks, "due_hoje", sem_tarefas)
    corpo = client.get("/abertura", headers=token(client)).json()
    assert corpo["hoje"]["tarefas_indisponivel"] is False


# --- vault_client: o módulo que NOMEIA arquivo estava no relógio do processo --


def test_o_path_do_raw_usa_o_fuso_do_leo(monkeypatch):
    """22h BRT num host UTC arquivava em D+1 enquanto a Daily que o referencia é D."""
    from datetime import datetime

    from app.tz import TZ

    # 2026-08-15 22:30 BRT = 2026-08-16 01:30 UTC.
    ts = datetime(2026, 8, 15, 22, 30, tzinfo=TZ).timestamp()
    capturado: dict = {}

    async def get(path):
        capturado["path"] = path
        return {"sha": "x"}  # já existe => write_raw devolve o path e não escreve

    monkeypatch.setattr(vault_client, "_get", get)
    import asyncio

    asyncio.run(vault_client.write_raw("texto", "c1", ts=ts))
    assert "2026-08-15" in capturado["path"], capturado["path"]

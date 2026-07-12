from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import anki, hermes_client, store
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


async def test_suggest_anki_filtra_resposta_e_delimita_notas(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)
    prompt_recebido = ""

    async def fake_oneshot(prompt: str) -> str:
        nonlocal prompt_recebido
        prompt_recebido = prompt
        return (
            'texto anterior [{"frente": "O que é entropia?", '
            '"meaning": "Medida de dispersão.", '
            '"example": "A entropia cresce no sistema isolado.", '
            '"hook": "Irreversibilidade."}, '
            '{"meaning": "sem frente"}, "lixo"] texto posterior'
        )

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    cards = await hermes_client.suggest_anki(
        "citação: entropia\ncomentário: lembrar da irreversibilidade"
    )

    notas_no_prompt = (
        prompt_recebido.rsplit("<notas>", 1)[1].split("</notas>", 1)[0]
    )
    assert notas_no_prompt == (
        "\ncitação: entropia\n"
        "comentário: lembrar da irreversibilidade\n"
    )
    assert cards == [
        {
            "frente": "O que é entropia?",
            "meaning": "Medida de dispersão.",
            "example": "A entropia cresce no sistema isolado.",
            "hook": "Irreversibilidade.",
        }
    ]


async def test_suggest_anki_sem_json_falha_sem_expor_payload(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)

    async def fake_oneshot(_prompt: str) -> str:
        return "resposta sem estrutura JSON"

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    with pytest.raises(RuntimeError, match="^anki_sem_json$"):
        await hermes_client.suggest_anki("citação: conteúdo privado")


async def test_suggest_anki_mock_nao_chama_cli(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", True)

    async def oneshot_nao_deveria_ser_chamado(_prompt: str) -> str:
        raise AssertionError("_oneshot não deveria ser chamado em modo mock")

    monkeypatch.setattr(
        hermes_client,
        "_oneshot",
        oneshot_nao_deveria_ser_chamado,
    )

    assert await hermes_client.suggest_anki("comentário: nota") == []


def test_endpoint_sugerir_persiste_com_sessao(client, monkeypatch):
    async def fake_suggest_anki(_notas: str) -> list[dict]:
        return [
            {
                "frente": "Frente",
                "meaning": "Meaning",
                "example": "Example",
                "hook": "Hook",
            }
        ]

    monkeypatch.setattr(hermes_client, "suggest_anki", fake_suggest_anki)

    response = client.post(
        "/anki/sugerir",
        json={"notas": "  comentário: uma nota  ", "session_id": 41},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["n"] == 1
    assert payload["cards"][0]["status"] == "sugerido"
    assert payload["cards"][0]["session_id"] == 41

    persistido = store.get_anki_card(payload["cards"][0]["id"])
    assert persistido is not None
    assert persistido["frente"] == "Frente"
    assert persistido["status"] == "sugerido"


def test_endpoint_sugerir_converte_falha_do_hermes_em_502(
    client,
    monkeypatch,
):
    async def fake_suggest_anki(_notas: str) -> list[dict]:
        raise RuntimeError("anki_sem_json")

    monkeypatch.setattr(hermes_client, "suggest_anki", fake_suggest_anki)

    response = client.post(
        "/anki/sugerir",
        json={"notas": "citação: nota", "session_id": None},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "anki_indisponivel"}


@pytest.mark.parametrize("notas", ["", " ", "\n\t"])
def test_endpoint_sugerir_rejeita_notas_vazias(client, notas):
    response = client.post(
        "/anki/sugerir",
        json={"notas": notas, "session_id": None},
    )

    assert response.status_code == 422


def test_endpoint_sugerir_aceita_zero_candidatos(client, monkeypatch):
    async def fake_suggest_anki(_notas: str) -> list[dict]:
        return []

    monkeypatch.setattr(hermes_client, "suggest_anki", fake_suggest_anki)

    response = client.post(
        "/anki/sugerir",
        json={"notas": "comentário: nada memorável", "session_id": 7},
    )

    assert response.status_code == 200
    assert response.json() == {"cards": [], "n": 0}


def test_crud_edita_e_valida_status(client):
    card = store.add_anki_cards(
        [{"frente": "Frente antiga", "meaning": "Significado"}]
    )[0]

    response = client.patch(
        f"/anki/cards/{card['id']}",
        json={"frente": "Frente editada", "deck": "Leituras"},
    )
    assert response.status_code == 200
    assert response.json()["frente"] == "Frente editada"
    assert response.json()["deck"] == "Leituras"

    response = client.patch(
        f"/anki/cards/{card['id']}",
        json={"status": "aprovado"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "aprovado"

    response = client.patch(
        f"/anki/cards/{card['id']}",
        json={"status": "exportado"},
    )
    assert response.status_code == 422

    response = client.patch(
        f"/anki/cards/{card['id']}",
        json={"status": "status-inexistente"},
    )
    assert response.status_code == 422

    response = client.get("/anki/cards", params={"status": "invalido"})
    assert response.status_code == 422

    response = client.patch(
        "/anki/cards/999999",
        json={"frente": "Não existe"},
    )
    assert response.status_code == 404


def test_exporta_apenas_aprovados_e_nao_repete(client):
    cards = store.add_anki_cards(
        [
            {
                "frente": "F1",
                "meaning": "M1",
                "example": "E1",
                "hook": "H1",
            },
            {
                "frente": "F2",
                "meaning": "M2",
                "example": "E2",
                "hook": "H2",
            },
            {
                "frente": "F3",
                "meaning": "M3",
                "example": "E3",
                "hook": "H3",
            },
            {
                "frente": "F4",
                "meaning": "M4",
                "example": "E4",
                "hook": "H4",
            },
        ]
    )
    store.update_anki_card(cards[0]["id"], status="aprovado")
    store.update_anki_card(cards[1]["id"], status="aprovado")
    store.update_anki_card(cards[3]["id"], status="descartado")

    response = client.post("/anki/export")

    assert response.status_code == 200
    payload = response.json()
    esperado = "F1\tM1\tE1\tH1\nF2\tM2\tE2\tH2\n"
    assert payload["n"] == 2
    assert payload["tsv"] == esperado
    assert payload["path"] is not None

    arquivo = Path(payload["path"])
    assert arquivo.exists()
    assert arquivo.read_text(encoding="utf-8") == esperado
    assert arquivo.parent == Path(settings.db_path).parent / "exports"

    assert store.get_anki_card(cards[0]["id"])["status"] == "exportado"
    assert store.get_anki_card(cards[1]["id"])["status"] == "exportado"
    assert store.get_anki_card(cards[2]["id"])["status"] == "sugerido"
    assert store.get_anki_card(cards[3]["id"])["status"] == "descartado"

    segunda_resposta = client.post("/anki/export")
    assert segunda_resposta.status_code == 200
    assert segunda_resposta.json() == {"n": 0, "path": None, "tsv": ""}


def test_tsv_limpa_tabs_e_quebras_sem_mudar_ordem_dos_campos():
    resultado = anki.tsv(
        [
            {
                "frente": "Frente\teditada",
                "meaning": "Linha 1\nLinha 2",
                "example": "Exemplo\r\nseguinte",
                "hook": "Gancho\rfinal",
            }
        ]
    )

    assert resultado == (
        "Frente editada\t"
        "Linha 1 Linha 2\t"
        "Exemplo seguinte\t"
        "Gancho final\n"
    )

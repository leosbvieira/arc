from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import pontos, store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


# Mesma razão da fixture homônima em `test_pontos.py`: estes testes são sobre a
# REGRA (o teto é compartilhado entre padrões de rotina e hábitos a reduzir, uma
# ocorrência não regride nível), e a regra não muda com o preço. A escala
# didática — rotina 1, desconto 3, teto 10 — mantém as contas legíveis; a tarifa
# de produção é travada em `test_pontos.py`, na seção "tarifa de produção".
@pytest.fixture(autouse=True)
def tarifa_didatica(monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_rotina", 1)
    monkeypatch.setattr(settings, "desconto_padrao", 3)
    monkeypatch.setattr(settings, "teto_desconto_semanal", 10)
    for campo in pontos._EVENTOS_PAGOS.values():
        if campo != "pontos_por_rotina":
            monkeypatch.setattr(settings, campo, 0)


def _create_habit(client, nome="Cafe depois das 18h", penalidade=1):
    response = client.post(
        "/habitos-reduzir",
        json={"nome": nome, "penalidade": penalidade},
    )
    assert response.status_code == 200
    return response.json()


def _record(client, habit_id, day, client_key=None):
    body = {
        "data": day,
        "client_key": client_key or f"test-{uuid4()}",
    }
    return client.post(f"/habitos-reduzir/{habit_id}/ocorrencias", json=body)


def test_crud_soft_delete_preserva_slug_e_valida_entrada(client):
    created = _create_habit(client, "  Cafe depois das 18h  ", 2)
    assert created["nome"] == "Cafe depois das 18h"
    assert created["penalidade"] == 2
    original_slug = created["slug"]

    assert client.get("/habitos-reduzir").json() == {"habitos": [created]}
    assert client.get(f"/habitos-reduzir/{created['id']}").json() == created

    updated = client.patch(
        f"/habitos-reduzir/{created['id']}",
        json={"nome": "Cafe tarde", "penalidade": 3},
    )
    assert updated.status_code == 200
    assert updated.json()["slug"] == original_slug
    assert updated.json()["nome"] == "Cafe tarde"
    assert updated.json()["penalidade"] == 3

    assert client.patch(f"/habitos-reduzir/{created['id']}", json={}).status_code == 422
    assert client.post(
        "/habitos-reduzir",
        json={"nome": "x", "penalidade": settings.teto_desconto_semanal + 1},
    ).status_code == 422

    deleted = client.delete(f"/habitos-reduzir/{created['id']}")
    assert deleted.status_code == 200
    assert client.get("/habitos-reduzir").json() == {"habitos": []}
    assert client.get(f"/habitos-reduzir/{created['id']}").status_code == 404
    assert client.delete(f"/habitos-reduzir/{created['id']}").status_code == 404


def test_ocorrencias_mesmo_dia_contam_uma_penalidade_e_undo_promove_proxima(client):
    habit = _create_habit(client, penalidade=2)
    today = date.today().isoformat()

    first = _record(client, habit["id"], today, "event-1")
    second = _record(client, habit["id"], today, "event-2")
    assert first.status_code == second.status_code == 200
    assert first.json()["ocorrencia"]["penalizavel"] is True
    assert second.json()["ocorrencia"]["penalizavel"] is False
    assert pontos.resumo()["semana"]["desconto"] == 2

    first_id = first.json()["ocorrencia"]["id"]
    second_id = second.json()["ocorrencia"]["id"]
    undone = client.post(f"/habitos-reduzir/ocorrencias/{first_id}/undo")
    assert undone.status_code == 200
    assert undone.json()["changed"] is True
    assert undone.json()["ocorrencia"]["desfeita"] is True
    assert pontos.resumo()["semana"]["desconto"] == 2

    history = client.get("/habitos-reduzir/historico").json()["ocorrencias"]
    by_id = {item["id"]: item for item in history}
    assert by_id[first_id]["penalizavel"] is False
    assert by_id[second_id]["penalizavel"] is True

    assert client.post(
        f"/habitos-reduzir/ocorrencias/{second_id}/undo"
    ).status_code == 200
    assert pontos.resumo()["semana"]["desconto"] == 0

    retry = client.post(f"/habitos-reduzir/ocorrencias/{second_id}/undo")
    assert retry.status_code == 200
    assert retry.json()["changed"] is False
    assert client.get(
        "/habitos-reduzir/historico?incluir_desfeitas=false"
    ).json() == {"ocorrencias": []}


def test_client_key_retry_idempotente_e_divergencia_falha_fechado(client):
    habit = _create_habit(client)
    today = date.today()
    first = _record(client, habit["id"], today.isoformat(), "same-key")
    retry = _record(client, habit["id"], today.isoformat(), "same-key")

    assert first.status_code == retry.status_code == 200
    assert first.json()["created"] is True
    assert retry.json()["created"] is False
    assert retry.json()["ocorrencia"]["id"] == first.json()["ocorrencia"]["id"]
    assert len(client.get("/habitos-reduzir/historico").json()["ocorrencias"]) == 1

    divergent = _record(
        client,
        habit["id"],
        (today + timedelta(days=1)).isoformat(),
        "same-key",
    )
    assert divergent.status_code == 409
    assert divergent.json() == {"detail": "reduction_client_key_divergente"}


def test_client_key_concorrente_cria_uma_linha(client):
    habit = _create_habit(client)
    today = date.today().isoformat()

    def record():
        return client.post(
            f"/habitos-reduzir/{habit['id']}/ocorrencias",
            json={"data": today, "client_key": "concurrent-key"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: record(), range(2)))

    assert all(response.status_code == 200 for response in results)
    assert sorted(response.json()["created"] for response in results) == [False, True]
    assert len({response.json()["ocorrencia"]["id"] for response in results}) == 1
    assert len(store.list_reduction_occurrences()) == 1


def test_registro_exige_client_key(client):
    habit = _create_habit(client)
    response = client.post(
        f"/habitos-reduzir/{habit['id']}/ocorrencias",
        json={"data": date.today().isoformat()},
    )
    assert response.status_code == 422


def test_pontos_endpoint_usa_semana_de_sao_paulo(client, monkeypatch):
    local_sunday = date(2026, 7, 12)
    habit = _create_habit(client)
    store.record_reduction_occurrence(habit["id"], local_sunday.isoformat())
    monkeypatch.setattr(pontos, "hoje_local", lambda: local_sunday)

    response = client.get("/pontos")

    assert response.status_code == 200
    assert response.json()["semana"]["desconto"] == 1


def test_historico_filtra_periodo_habito_e_desfeitas(client):
    first_habit = _create_habit(client, "Acucar", 1)
    second_habit = _create_habit(client, "Redes sociais", 1)
    base = date(2026, 7, 6)
    first = _record(client, first_habit["id"], base.isoformat()).json()["ocorrencia"]
    _record(client, first_habit["id"], (base + timedelta(days=1)).isoformat())
    _record(client, second_habit["id"], (base + timedelta(days=1)).isoformat())
    client.post(f"/habitos-reduzir/ocorrencias/{first['id']}/undo")

    response = client.get(
        "/habitos-reduzir/historico",
        params={
            "desde": (base + timedelta(days=1)).isoformat(),
            "ate": (base + timedelta(days=1)).isoformat(),
            "habito_id": first_habit["id"],
            "incluir_desfeitas": "false",
        },
    )
    assert response.status_code == 200
    occurrences = response.json()["ocorrencias"]
    assert len(occurrences) == 1
    assert occurrences[0]["habito_id"] == first_habit["id"]
    assert occurrences[0]["data"] == (base + timedelta(days=1)).isoformat()

    assert client.get(
        "/habitos-reduzir/historico",
        params={"desde": "2026-07-08", "ate": "2026-07-07"},
    ).json() == {"detail": "periodo_invalido"}


def test_pontos_aplica_penalidade_versionada_por_dia_e_semana(client):
    habit = _create_habit(client, penalidade=1)
    monday = date(2026, 7, 6)
    store.record_reduction_occurrence(habit["id"], monday.isoformat())
    store.record_reduction_occurrence(habit["id"], monday.isoformat())

    store.update_reduction_habit(habit["id"], penalidade=3)
    store.record_reduction_occurrence(
        habit["id"],
        (monday + timedelta(days=1)).isoformat(),
    )

    current = pontos.resumo(hoje=monday + timedelta(days=2))
    assert current["semana"]["desconto"] == 4
    assert current["semana"]["saldo"] == 0
    assert current["saldo_total"] == current["ciclo"]["pontos"] == 0

    store.record_reduction_occurrence(
        habit["id"],
        (monday + timedelta(days=7)).isoformat(),
    )
    following = pontos.resumo(hoje=monday + timedelta(days=7))
    assert following["semana"]["desconto"] == 3
    assert following["semana"]["saldo"] == 0
    assert following["saldo_total"] == following["ciclo"]["pontos"] == 0


def test_ajuste_reduz_saldo_existente_sem_criar_divida(client):
    monday = date(2026, 7, 6)
    for index in range(5):
        store.record_checks(
            monday.isoformat(),
            "yoga",
            [(f"ganho-{index}", True)],
        )

    habit = _create_habit(client, penalidade=3)
    store.record_reduction_occurrence(
        habit["id"],
        (monday + timedelta(days=7)).isoformat(),
    )
    summary = pontos.resumo(hoje=monday + timedelta(days=7))

    assert summary["semana"] == {
        "ganho": 0,
        "desconto": 3,
        "saldo": 0,
        "padroes": [],
        "teto_desconto": settings.teto_desconto_semanal,
    }
    assert summary["saldo_total"] == 2
    assert summary["ciclo"]["pontos"] == 2


def test_teto_semanal_e_compartilhado_com_padroes_de_rotina(client):
    monday = date(2026, 7, 6)
    for slug in ("academia", "diario", "pesagem"):
        for offset in range(3):
            store.record_checks(
                (monday + timedelta(days=offset)).isoformat(),
                "yoga",
                [(slug, False)],
            )

    habit = _create_habit(client, penalidade=3)
    store.record_reduction_occurrence(
        habit["id"],
        (monday + timedelta(days=2)).isoformat(),
    )
    summary = pontos.resumo(hoje=monday + timedelta(days=3))["semana"]

    assert sum(-item["delta"] for item in summary["padroes"]) == 9
    assert summary["desconto"] == settings.teto_desconto_semanal == 10
    assert summary["teto_desconto"] == 10
    assert summary["saldo"] == 0


def test_ocorrencia_nao_regride_nivel_ja_conquistado(client, monkeypatch):
    monday = date(2026, 7, 6)
    monkeypatch.setattr(settings, "nivel_limiares", [5, 10, 20, 40])
    for index in range(5):
        store.record_checks(
            monday.isoformat(),
            "yoga",
            [(f"nivel-{index}", True)],
        )

    before = pontos.resumo(hoje=monday)
    assert (before["saldo_total"], before["pico_total"], before["nivel"]) == (5, 5, 1)

    habit = _create_habit(client, penalidade=3)
    store.record_reduction_occurrence(habit["id"], monday.isoformat())
    after = pontos.resumo(hoje=monday)

    assert after["saldo_total"] == 2
    assert after["pico_total"] == 5
    assert after["nivel"] == 1


def test_delete_bloqueia_nova_ocorrencia_sem_apagar_historico_ou_pontos(client):
    habit = _create_habit(client, penalidade=2)
    today = date.today().isoformat()
    recorded = _record(client, habit["id"], today)
    assert recorded.status_code == 200
    assert client.delete(f"/habitos-reduzir/{habit['id']}").status_code == 200

    blocked = _record(client, habit["id"], today)
    assert blocked.status_code == 404
    assert blocked.json() == {"detail": "habito_reduzir_nao_encontrado"}
    history = client.get("/habitos-reduzir/historico").json()["ocorrencias"]
    assert len(history) == 1 and history[0]["nome"] == habit["nome"]
    assert pontos.resumo()["semana"]["desconto"] == 2


def test_contrato_usa_linguagem_neutra_e_exige_auth(client):
    habit = _create_habit(client)
    occurrence = _record(client, habit["id"], date.today().isoformat()).json()
    text = json.dumps(occurrence, ensure_ascii=False).lower()
    for term in ("fracasso", "vergonha", "recaida", "recaída", "falhou"):
        assert term not in text

    override = app.dependency_overrides.pop(require_auth)
    try:
        unauthenticated = TestClient(app)
        assert unauthenticated.get("/habitos-reduzir").status_code in (401, 403)
        assert unauthenticated.post(
            "/habitos-reduzir",
            json={"nome": "Teste", "penalidade": 1},
        ).status_code in (401, 403)
        assert unauthenticated.get(
            "/habitos-reduzir/historico"
        ).status_code in (401, 403)
    finally:
        app.dependency_overrides[require_auth] = override

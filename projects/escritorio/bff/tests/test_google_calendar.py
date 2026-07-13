import asyncio
import json
import re
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app import google_calendar, store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "google_calendar_client_id", "client-id")
    monkeypatch.setattr(settings, "google_calendar_client_secret", "client-secret")
    monkeypatch.setattr(settings, "google_calendar_refresh_token", "refresh-token")
    monkeypatch.setattr(settings, "google_calendar_id", "leo@example.com")
    monkeypatch.setattr(settings, "google_calendar_timeout", 3)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "google_calendar_client_id", "")
    monkeypatch.setattr(settings, "google_calendar_client_secret", "")
    monkeypatch.setattr(settings, "google_calendar_refresh_token", "")
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_event_id_deterministico_e_valido_para_google():
    primeiro = google_calendar.event_id_for("gcal-client-key-123")
    segundo = google_calendar.event_id_for("gcal-client-key-123")

    assert primeiro == segundo
    assert 5 <= len(primeiro) <= 1024
    assert re.fullmatch(r"[0-9a-v]+", primeiro)


def test_cria_evento_via_oauth_refresh_sem_rede(configured):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == google_calendar.TOKEN_URL:
            form = parse_qs(request.content.decode())
            assert form == {
                "client_id": ["client-id"],
                "client_secret": ["client-secret"],
                "refresh_token": ["refresh-token"],
                "grant_type": ["refresh_token"],
            }
            return httpx.Response(200, json={"access_token": "access-token"})

        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer access-token"
        assert "leo%40example.com/events" in str(request.url)
        payload = json.loads(request.content)
        assert payload["id"] == google_calendar.event_id_for("gcal-key-0001")
        assert payload["summary"] == "Consulta"
        assert payload["start"]["dateTime"] == "2026-07-15T14:30:00-03:00"
        assert payload["end"]["dateTime"] == "2026-07-15T15:15:00-03:00"
        assert payload["start"]["timeZone"] == "America/Sao_Paulo"
        return httpx.Response(
            200,
            json={
                "id": payload["id"],
                "summary": payload["summary"],
                "htmlLink": "https://calendar.google.com/event?id=safe",
            },
        )

    evento = asyncio.run(
        google_calendar.create_event(
            "Consulta",
            "2026-07-15",
            "14:30",
            45,
            "gcal-key-0001",
            transport=httpx.MockTransport(handler),
        )
    )

    assert evento["id"] == google_calendar.event_id_for("gcal-key-0001")
    assert evento["fonte"] == "gcal"
    assert len(requests) == 2


def test_retry_apos_perda_de_resposta_reconcilia_409_sem_duplicar(configured):
    state = {"posts": 0, "gets": 0, "event_id": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == google_calendar.TOKEN_URL:
            return httpx.Response(200, json={"access_token": "access-token"})

        if request.method == "POST":
            state["posts"] += 1
            payload = json.loads(request.content)
            state["event_id"] = payload["id"]
            if state["posts"] == 1:
                raise httpx.ReadTimeout("response lost", request=request)
            return httpx.Response(409, json={"error": {"message": "Already Exists"}})

        state["gets"] += 1
        assert request.url.path.endswith(f"/events/{state['event_id']}")
        return httpx.Response(
            200,
            json={
                "id": state["event_id"],
                "summary": "Consulta",
                "start": {"dateTime": "2026-07-15T14:30:00-03:00"},
                "end": {"dateTime": "2026-07-15T15:15:00-03:00"},
            },
        )

    transport = httpx.MockTransport(handler)
    args = ("Consulta", "2026-07-15", "14:30", 45, "gcal-key-retry")

    with pytest.raises(google_calendar.GoogleCalendarUnavailable):
        asyncio.run(google_calendar.create_event(*args, transport=transport))

    evento = asyncio.run(google_calendar.create_event(*args, transport=transport))

    assert evento["id"] == state["event_id"]
    assert state["posts"] == 2
    assert state["gets"] == 1


def test_mesma_client_key_com_payload_diferente_nao_reconcilia(configured):
    event_id = google_calendar.event_id_for("gcal-key-conflict")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == google_calendar.TOKEN_URL:
            return httpx.Response(200, json={"access_token": "access-token"})
        if request.method == "POST":
            return httpx.Response(409, json={"error": {"message": "Already Exists"}})
        return httpx.Response(
            200,
            json={
                "id": event_id,
                "summary": "Evento anterior",
                "start": {"dateTime": "2026-07-15T10:00:00-03:00"},
                "end": {"dateTime": "2026-07-15T11:00:00-03:00"},
            },
        )

    with pytest.raises(google_calendar.GoogleCalendarIdempotencyConflict):
        asyncio.run(
            google_calendar.create_event(
                "Evento novo",
                "2026-07-15",
                "14:30",
                45,
                "gcal-key-conflict",
                transport=httpx.MockTransport(handler),
            )
        )


def test_endpoint_degrada_503_quando_oauth_nao_configurado(client):
    response = client.post(
        "/agenda/google-calendar",
        json={
            "titulo": "Consulta",
            "data": "2026-07-15",
            "hora": "14:30",
            "duracao_min": 45,
            "client_key": "gcal-key-0001",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "google_calendar_nao_configurado"


@pytest.mark.parametrize(
    "patch",
    [
        {"titulo": "   "},
        {"data": "15/07/2026"},
        {"hora": "25:00"},
        {"duracao_min": 0},
        {"client_key": "bad key"},
    ],
)
def test_endpoint_valida_evento_antes_de_chamar_google(client, patch):
    body = {
        "titulo": "Consulta",
        "data": "2026-07-15",
        "hora": "14:30",
        "duracao_min": 45,
        "client_key": "gcal-key-0001",
        **patch,
    }

    assert client.post("/agenda/google-calendar", json=body).status_code == 422

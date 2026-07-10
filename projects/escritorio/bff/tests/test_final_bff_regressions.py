import hashlib
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import clickup_client, main, store, tasks, telegram
from app.config import DEFAULTS, settings


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    main.app.dependency_overrides[main.require_auth] = lambda: None
    client = TestClient(main.app, raise_server_exceptions=False)
    yield client
    client.close()
    main.app.dependency_overrides.clear()


def test_retry_failed_endpoint_reapresenta_item(api_client):
    capture_id = store.enqueue_capture(
        "conteúdo de teste",
        None,
        "retry-failed-1",
    )
    store.mark_capture(
        capture_id,
        status="failed",
        error="RuntimeError",
    )

    response = api_client.post("/captures/retry-failed")

    assert response.status_code == 200
    assert response.json() == {"requeued": 1}
    assert store.failed_captures() == []
    pending = store.pending_captures()
    assert [item["id"] for item in pending] == [capture_id]
    assert pending[0]["attempts"] == 0


def test_count_events_since_deduplica_ref(api_client):
    store.log_event("closing_approved", ref="2026-07-09")
    store.log_event("closing_approved", ref="2026-07-09")

    assert store.count_events_since("closing_approved", 0) == 1


def test_closing_raw_id_depende_do_conteudo_e_retry_reusa_id(
    api_client,
    monkeypatch,
):
    calls = []
    unique_writes = {}

    async def fake_write_raw(text, capture_id):
        calls.append(capture_id)
        unique_writes.setdefault(capture_id, text)
        return f"1- Inbox/Raw/raw-c{capture_id}.md"

    async def fake_append_file(
        path,
        content,
        message,
        *,
        header_if_new=None,
        dedupe_marker=None,
    ):
        return path

    monkeypatch.setattr(main.vault_client, "write_raw", fake_write_raw)
    monkeypatch.setattr(main.vault_client, "append_file", fake_append_file)

    first = {
        "raw_text": "primeiro despejo",
        "draft_md": "primeiro fechamento",
        "checks": [],
    }
    second = {
        "raw_text": "segundo despejo",
        "draft_md": "segundo fechamento",
        "checks": [],
    }

    assert api_client.post("/closing/approve", json=first).status_code == 200
    assert api_client.post("/closing/approve", json=second).status_code == 200
    assert api_client.post("/closing/approve", json=first).status_code == 200

    today = date.today().isoformat()
    first_id = (
        f"f{today}-"
        f"{hashlib.sha1(first['raw_text'].encode('utf-8')).hexdigest()[:8]}"
    )
    second_id = (
        f"f{today}-"
        f"{hashlib.sha1(second['raw_text'].encode('utf-8')).hexdigest()[:8]}"
    )

    assert calls == [first_id, second_id, first_id]
    assert len(unique_writes) == 2


@pytest.mark.parametrize("field", sorted(DEFAULTS))
def test_guard_rejeita_cada_segredo_default(monkeypatch, field):
    for secret_field in DEFAULTS:
        monkeypatch.setattr(
            settings,
            secret_field,
            f"valor-seguro-{secret_field}",
        )
    monkeypatch.setattr(settings, field, DEFAULTS[field])

    with pytest.raises(RuntimeError, match="segredos default detectados"):
        main._guard_default_secrets()


async def test_fetch_e_count_reusam_client_e_count_exclui_staging(
    monkeypatch,
):
    instances = []
    calls = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"tasks": [{"date_done": "123"}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            instances.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, *, params=None, headers=None):
            calls.append((url, dict(params or {})))
            return FakeResponse()

    monkeypatch.setattr(
        clickup_client,
        "AREA_LISTS",
        {
            "Trabalho": "list-work",
            "Staging": "list-staging",
            "Corpo": "list-body",
        },
    )
    monkeypatch.setattr(clickup_client.httpx, "AsyncClient", FakeClient)

    await clickup_client.fetch_open()

    assert len(instances) == 1
    assert [url.rsplit("/", 2)[-2] for url, _ in calls] == [
        "list-work",
        "list-staging",
        "list-body",
    ]

    instances.clear()
    calls.clear()

    count = await clickup_client.count_closed_since(123456)

    assert count == 2
    assert len(instances) == 1
    assert [url.rsplit("/", 2)[-2] for url, _ in calls] == [
        "list-work",
        "list-body",
    ]
    for _, params in calls:
        assert params == {
            "archived": "false",
            "subtasks": "false",
            "include_closed": "true",
            "date_done_gt": "123456",
        }


async def test_complete_recusa_task_de_lista_estrangeira_sem_put(
    monkeypatch,
):
    put_calls = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"list": {"id": "lista-estrangeira"}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, *, headers=None):
            return FakeResponse()

        async def put(self, url, *, json=None, headers=None):
            put_calls.append((url, json))
            return FakeResponse()

    monkeypatch.setattr(clickup_client.httpx, "AsyncClient", FakeClient)

    assert await clickup_client.complete("task-foreign") is False
    assert put_calls == []


async def test_get_detail_recusa_task_de_lista_estrangeira(monkeypatch):
    monkeypatch.setattr(settings, "tasks_source", "clickup")
    monkeypatch.setattr(settings, "clickup_token", "token-de-teste")

    async def fake_get_task(task_id):
        return {
            "id": task_id,
            "name": "não deve ser exposta",
            "list": {"id": "lista-estrangeira"},
        }

    monkeypatch.setattr(clickup_client, "get_task", fake_get_task)

    assert await tasks.get_detail("task-foreign") is None


def test_render_digest_sanitiza_quebra_de_linha_no_nome(monkeypatch):
    monkeypatch.setattr(settings, "sensitive_areas", "")
    item = tasks.Task(
        id="t-newline",
        name="primeira linha\nlinha injetada",
        area="Trabalho",
        days_overdue=1,
        severity="leve",
    )

    rendered = tasks.render_digest_lines([item], "telegram")

    assert rendered == [
        "🟠 primeira linha linha injetada · Trabalho (1d de atraso)",
    ]


async def test_telegram_converte_excecao_nao_http_em_false(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "token-de-teste")
    monkeypatch.setattr(settings, "telegram_chat_id", "chat-de-teste")

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise ValueError("falha sintética")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(telegram.httpx, "AsyncClient", BrokenClient)

    assert await telegram.send("mensagem neutra") is False

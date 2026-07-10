import asyncio
import time
from datetime import datetime, time as datetime_time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import clickup_client, main, store, tasks
from app.auth import require_auth
from app.config import settings


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    store.record_checks(
        "2026-07-06",
        "yoga",
        [("academia", True), ("yoga", True)],
    )
    store.record_checks(
        "2026-07-07",
        "yoga",
        [("academia", False), ("yoga", True)],
    )
    store.log_event("closing_approved", ref="2026-07-06")
    store.log_event("closing_approved", ref="2026-07-07")
    store.log_event("capture_done", ref="1")
    store.add_session(
        "leitura",
        "Antifragil",
        "leitura",
        time.time() - 3600,
        time.time() - 1800,
        1800,
        10,
        "Antifragil",
    )


def test_pack_calcula_scorecard(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    pack = tasks.weekly_review_pack(today="2026-07-08")

    assert pack["week"] == "2026-W28"
    assert pack["desde"] == "2026-07-06"
    assert pack["scorecard"]["por_rotina"]["academia"] == {
        "feitos": 1,
        "dias": 2,
    }
    assert pack["scorecard"]["pct"] == 75
    assert pack["dailies"] == 2
    assert pack["capturas"] == 1
    assert pack["sessoes_leitura"] == {"n": 1, "min_total": 30}
    assert pack["tarefas_concluidas"] is None
    assert pack["staging_pendentes"] is None


def test_pack_sem_dados_nao_quebra(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()

    pack = tasks.weekly_review_pack(today="2026-07-08")

    assert pack["scorecard"] == {"pct": 0, "por_rotina": {}}
    assert pack["dailies"] == 0
    assert pack["capturas"] == 0
    assert pack["sessoes_leitura"] == {"n": 0, "min_total": 0}


def test_texto_do_review(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    text = tasks.weekly_review_text(today="2026-07-08")

    assert "scorecard" in text.lower()
    assert "75%" in text
    assert "academia 1/2" in text
    assert "dailies 2/7" in text
    assert "leitura 1 sessões (30 min)" in text


def test_endpoint_enriquece_pack_com_clickup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    called = {}

    async def fake_count_closed_since(ts_ms):
        called["ts_ms"] = ts_ms
        return 8

    async def fake_count_open(list_id):
        called["list_id"] = list_id
        return 3

    monkeypatch.setattr(
        clickup_client,
        "count_closed_since",
        fake_count_closed_since,
    )
    monkeypatch.setattr(clickup_client, "count_open", fake_count_open)
    main.app.dependency_overrides[require_auth] = lambda: "test"

    client = TestClient(main.app)
    try:
        response = client.get("/review/weekly")
    finally:
        client.close()
        main.app.dependency_overrides.pop(require_auth, None)

    assert response.status_code == 200
    assert response.json()["tarefas_concluidas"] == 8
    assert response.json()["staging_pendentes"] == 3
    assert called["list_id"] == clickup_client.AREA_LISTS[
        clickup_client.STAGING
    ]

    local_tz = ZoneInfo("America/Sao_Paulo")
    today = datetime.now(local_tz).date()
    monday = today - timedelta(days=today.weekday())
    expected_ts_ms = int(
        datetime.combine(
            monday,
            datetime_time.min,
            tzinfo=local_tz,
        ).astimezone(timezone.utc).timestamp()
        * 1000,
    )
    assert called["ts_ms"] == expected_ts_ms


def test_clickup_contagens_usam_fetch_list(monkeypatch):
    calls = []

    async def fake_fetch_list(list_id, params=None, *, client=None):
        calls.append((list_id, params))
        if params is None:
            return [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        return [
            {"id": "done", "date_done": "1783566000000"},
            {"id": "open", "date_done": None},
        ]

    monkeypatch.setattr(clickup_client, "_fetch_list", fake_fetch_list)

    assert asyncio.run(clickup_client.count_open("staging-list")) == 3
    # W11: count_closed_since exclui a lista de triagem Staging.
    assert asyncio.run(clickup_client.count_closed_since(123456)) == (
        len(clickup_client.AREA_LISTS) - 1
    )
    assert calls[0] == ("staging-list", None)
    assert all(
        params == {
            "include_closed": "true",
            "date_done_gt": "123456",
        }
        for _, params in calls[1:]
    )


def test_complete_registra_telemetria_no_sucesso(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(tasks, "_use_clickup", lambda: False)
    store.init_db()

    created = asyncio.run(tasks.create("Tarefa para concluir", "Trabalho"))

    assert asyncio.run(tasks.complete(created.id)) is True
    assert store.count_events_since("task_completed", 0) == 1

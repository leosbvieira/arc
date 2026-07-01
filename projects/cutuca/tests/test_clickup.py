from datetime import date

import pytest
from fakes import FakeResponse, FakeSession

from cutuca.clickup import ClickUpClient, ClickUpError
from cutuca.timeutil import get_tz, iso_to_ms

TZ = get_tz("UTC")

# Derive ms from dates via the same tz so the adapter round-trip is what's asserted.
DUE_MS = iso_to_ms("2026-07-03", TZ)
UPDATED_MS = iso_to_ms("2026-06-28", TZ)


def test_create_task_posts_body():
    captured = {}

    def handler(method, url, kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeResponse({"id": "abc", "name": kwargs["json"]["name"], "status": {"status": "open"}})

    client = ClickUpClient("pk_x", tz=TZ, session=FakeSession(handler))
    task = client.create_task("LIST1", "enviar relatório", assignee_ids=[99], due_date_ms=DUE_MS)

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/list/LIST1/task")
    assert captured["json"]["name"] == "enviar relatório"
    assert captured["json"]["assignees"] == [99]
    assert captured["json"]["due_date"] == DUE_MS
    assert task.id == "abc"
    assert task.status == "open"


def test_list_tasks_adapts_fields():
    def handler(method, url, kwargs):
        return FakeResponse({
            "last_page": True,
            "tasks": [{
                "id": "t1",
                "name": "corrigir bug",
                "assignees": [{"username": "Ana", "id": 1}],
                "due_date": str(DUE_MS),
                "date_updated": str(UPDATED_MS),
                "status": {"status": "in progress"},
                "url": "http://x/t1",
            }],
        })

    client = ClickUpClient("pk_x", tz=TZ, session=FakeSession(handler))
    tasks = client.list_tasks("LIST1")
    assert len(tasks) == 1
    t = tasks[0]
    assert t.id == "t1"
    assert t.assignees == ["Ana"]
    assert t.due_date == date(2026, 7, 3)
    assert t.last_update == date(2026, 6, 28)
    assert t.status == "in progress"


def test_list_tasks_paginates():
    pages = {
        0: {"last_page": False, "tasks": [{"id": "a", "name": "a"}]},
        1: {"last_page": True, "tasks": [{"id": "b", "name": "b"}]},
    }

    def handler(method, url, kwargs):
        page = kwargs.get("params", {}).get("page", 0)
        return FakeResponse(pages[page])

    client = ClickUpClient("pk_x", tz=TZ, session=FakeSession(handler))
    ids = [t.id for t in client.list_tasks("LIST1")]
    assert ids == ["a", "b"]


def test_http_error_raises():
    def handler(method, url, kwargs):
        return FakeResponse(status_code=401, text="unauthorized")

    client = ClickUpClient("pk_bad", tz=TZ, session=FakeSession(handler))
    with pytest.raises(ClickUpError):
        client.list_tasks("LIST1")


def test_resolve_assignees_uses_overrides_without_network():
    def handler(method, url, kwargs):  # would only be hit if overrides missed
        raise AssertionError("should not call network when override matches")

    client = ClickUpClient("pk_x", tz=TZ, session=FakeSession(handler))
    ids = client.resolve_assignees(["João"], "LIST1", overrides={"joão": 555})
    assert ids == [555]


def test_resolve_assignees_matches_member():
    def handler(method, url, kwargs):
        assert url.endswith("/list/LIST1/member")
        return FakeResponse({"members": [{"user": {"id": 7, "username": "ana silva", "email": "ana@x.com"}}]})

    client = ClickUpClient("pk_x", tz=TZ, session=FakeSession(handler))
    assert client.resolve_assignees(["Ana"], "LIST1") == [7]
    assert client.resolve_assignees(["ninguém"], "LIST1") == []

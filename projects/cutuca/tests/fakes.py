"""Test doubles: no network anywhere. Each fake mimics only the surface its
collaborator actually uses."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Optional

from cutuca.models import Task


# ------------------------------- anthropic ---------------------------------

class _Block:
    def __init__(self, text: str):
        self.text = text


class _Resp:
    def __init__(self, text: str):
        self.content = [_Block(text)]


class _Messages:
    def __init__(self, text: str = "", raiser: Optional[Exception] = None):
        self._text = text
        self._raiser = raiser
        self.calls: list[dict] = []

    def create(self, **kwargs) -> _Resp:
        self.calls.append(kwargs)
        if self._raiser is not None:
            raise self._raiser
        return _Resp(self._text)


class FakeAnthropic:
    """Object exposing .messages.create(...) like the real SDK client."""

    def __init__(self, text: str = "", raiser: Optional[Exception] = None):
        self.messages = _Messages(text, raiser)


# ----------------------------- requests session ----------------------------

class FakeResponse:
    def __init__(self, json_data: Any = None, status_code: int = 200, text: str = ""):
        self._json = json_data
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeSession:
    """Routes .request/.post/.get through a single handler(method, url, kwargs)."""

    def __init__(self, handler: Callable[[str, str, dict], FakeResponse]):
        self.handler = handler
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.handler(method, url, kwargs)

    def post(self, url: str, **kwargs) -> FakeResponse:
        return self.request("POST", url, **kwargs)

    def get(self, url: str, **kwargs) -> FakeResponse:
        return self.request("GET", url, **kwargs)


# ------------------------------ clickup client -----------------------------

class FakeClickUp:
    def __init__(
        self,
        *,
        tasks: Optional[list[Task]] = None,
        assignee_ids: Optional[list[int]] = None,
        raise_on_create: bool = False,
    ):
        self._tasks = tasks or []
        self._assignee_ids = assignee_ids if assignee_ids is not None else [123]
        self.raise_on_create = raise_on_create
        self.created: list[dict] = []

    def resolve_assignees(self, names, list_id, overrides=None) -> list[int]:
        return list(self._assignee_ids)

    def create_task(self, list_id, name, *, assignee_ids=None, due_date_ms=None, **kw) -> Task:
        if self.raise_on_create:
            raise RuntimeError("clickup boom")
        rec = {"list_id": list_id, "name": name, "assignee_ids": assignee_ids, "due_date_ms": due_date_ms}
        self.created.append(rec)
        return Task(id="new-1", name=name, assignees=[], due_date=None, last_update=None, status="open")

    def list_tasks(self, list_id, **kw) -> list[Task]:
        return list(self._tasks)


# --------------------------------- channel ---------------------------------

class FakeChannel:
    def __init__(self, fail: bool = False):
        self.sent: list[tuple[Any, str]] = []
        self.fail = fail

    def send(self, chat_id, text) -> dict:
        if self.fail:
            raise RuntimeError("send boom")
        self.sent.append((chat_id, text))
        return {"ok": True}

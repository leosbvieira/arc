"""ClickUp API v2 client. Thin REST wrapper with timeouts + light retry. The raw->Task
adapter is the single place API shape is interpreted (design decision D-3).

Session is injectable (any object with .get/.post) so tests never hit the network.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .models import Task
from .timeutil import ms_to_date

BASE_URL = "https://api.clickup.com/api/v2"
_RETRY_STATUS = {429, 500, 502, 503, 504}


class ClickUpError(RuntimeError):
    pass


class ClickUpClient:
    def __init__(
        self,
        token: str,
        *,
        tz=None,
        timeout: float = 15,
        session: Any = None,
        max_retries: int = 2,
        backoff: float = 0.5,
    ):
        self.token = token
        self.tz = tz  # tzinfo for date conversion; UTC if None
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        if session is not None:
            self.session = session
        else:
            import requests  # lazy

            self.session = requests.Session()

    # ------------------------------- transport -------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{BASE_URL}{path}"
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("headers", self._headers())
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, **kwargs)
            except Exception as exc:  # network error (requests.RequestException etc.)
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff * (attempt + 1))
                    continue
                raise ClickUpError(f"network error calling {method} {path}: {exc}") from exc

            status = getattr(resp, "status_code", 200)
            if status in _RETRY_STATUS and attempt < self.max_retries:
                time.sleep(self.backoff * (attempt + 1))
                continue
            if status >= 400:
                body = _safe_text(resp)
                raise ClickUpError(f"{method} {path} -> {status}: {body}")
            return _safe_json(resp)
        raise ClickUpError(f"exhausted retries for {method} {path}: {last_exc}")

    # --------------------------------- reads ---------------------------------

    def list_tasks(self, list_id: str, *, include_closed: bool = False) -> list[Task]:
        """All tasks in a list, paginated, adapted into Task objects."""
        tasks: list[Task] = []
        page = 0
        while True:
            data = self._request(
                "GET",
                f"/list/{list_id}/task",
                params={
                    "page": page,
                    "include_closed": str(include_closed).lower(),
                    "subtasks": "true",
                },
            )
            batch = data.get("tasks", [])
            tasks.extend(self._to_task(raw) for raw in batch)
            if data.get("last_page") is True or len(batch) == 0:
                break
            page += 1
            if page > 50:  # hard safety stop
                break
        return tasks

    def get_members(self, list_id: str) -> list[dict]:
        data = self._request("GET", f"/list/{list_id}/member")
        return data.get("members", [])

    # --------------------------------- writes --------------------------------

    def create_task(
        self,
        list_id: str,
        name: str,
        *,
        assignee_ids: Optional[list[int]] = None,
        due_date_ms: Optional[int] = None,
        status: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Task:
        body: dict[str, Any] = {"name": name}
        if assignee_ids:
            body["assignees"] = assignee_ids
        if due_date_ms is not None:
            body["due_date"] = due_date_ms
            body["due_date_time"] = False
        if status:
            body["status"] = status
        if description:
            body["description"] = description
        raw = self._request("POST", f"/list/{list_id}/task", json=body)
        return self._to_task(raw)

    # ------------------------------ assignees --------------------------------

    def resolve_assignees(
        self,
        names: list[str],
        list_id: str,
        overrides: Optional[dict[str, int]] = None,
    ) -> list[int]:
        """Map display names -> ClickUp user ids. Overrides win; otherwise match the
        list's members case-insensitively by username/email. Unmatched names are
        skipped (caller may still create an unassigned task)."""
        overrides = {k.lower(): v for k, v in (overrides or {}).items()}
        wanted = [n for n in names if n]
        if not wanted:
            return []

        ids: list[int] = []
        members: Optional[list[dict]] = None
        for name in wanted:
            key = name.strip().lower()
            if key in overrides:
                ids.append(int(overrides[key]))
                continue
            if members is None:
                members = self.get_members(list_id)
            match = _match_member(members, key)
            if match is not None:
                ids.append(int(match))
        return ids

    # -------------------------------- adapter --------------------------------

    def _to_task(self, raw: dict) -> Task:
        status = raw.get("status")
        if isinstance(status, dict):
            status = status.get("status")
        assignees = [
            (a.get("username") or a.get("email") or str(a.get("id")))
            for a in (raw.get("assignees") or [])
        ]
        return Task(
            id=str(raw.get("id")),
            name=raw.get("name", ""),
            assignees=assignees,
            due_date=ms_to_date(raw.get("due_date"), self.tz),
            last_update=ms_to_date(raw.get("date_updated"), self.tz),
            status=status,
            url=raw.get("url"),
        )


# --------------------------------- helpers ---------------------------------

def _match_member(members: list[dict], key: str) -> Optional[int]:
    for m in members:
        user = m.get("user", m)  # /list/{}/member returns {user: {...}} shapes vary
        username = (user.get("username") or "").strip().lower()
        email = (user.get("email") or "").strip().lower()
        if key == username or key == email or (username and key in username):
            return user.get("id")
    return None


def _safe_json(resp: Any) -> dict:
    try:
        data = resp.json()
    except Exception as exc:
        raise ClickUpError(f"invalid JSON response: {exc}") from exc
    return data if isinstance(data, dict) else {"tasks": data}


def _safe_text(resp: Any) -> str:
    return getattr(resp, "text", "") or ""

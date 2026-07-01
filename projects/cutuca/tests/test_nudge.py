from datetime import date, timedelta

from fakes import FakeChannel, FakeClickUp

from cutuca.config import Config
from cutuca.models import Task
from cutuca.nudge import format_digest, run_digest
from cutuca.state import NudgeState

TODAY = date(2026, 6, 30)


def mk(id, **kw) -> Task:
    base = dict(name=f"task {id}", assignees=["joão"], due_date=None,
                last_update=None, status="open")
    base.update(kw)
    return Task(id=id, **base)


def cfg(owner=1234) -> Config:
    c = Config()
    c.clickup.list_id = "LIST1"
    c.owner_chat_id = owner
    return c


def _tasks():
    return [
        mk("a", due_date=TODAY),                        # due today
        mk("b", due_date=TODAY - timedelta(days=8)),    # very overdue
        mk("c", due_date=TODAY + timedelta(days=30)),   # not due -> excluded
    ]


def test_digest_sends_selected_and_dedupes(tmp_path):
    clickup = FakeClickUp(tasks=_tasks())
    channel = FakeChannel()
    with NudgeState(str(tmp_path / "s.db")) as state:
        r1 = run_digest(clickup=clickup, channel=channel, state=state, config=cfg(), today=TODAY)
        assert r1.sent is True
        assert r1.count == 2                     # a, b (c excluded)
        assert len(channel.sent) == 1

        # second run same day -> nothing new
        r2 = run_digest(clickup=clickup, channel=channel, state=state, config=cfg(), today=TODAY)
        assert r2.sent is False
        assert r2.count == 0
        assert len(channel.sent) == 1            # no extra send

        # next day -> reappears (persistence)
        r3 = run_digest(clickup=clickup, channel=channel, state=state, config=cfg(),
                        today=TODAY + timedelta(days=1))
        assert r3.sent is True
        assert r3.count == 2


def test_tone_marker_present_when_escala_on(tmp_path):
    clickup = FakeClickUp(tasks=[mk("b", due_date=TODAY - timedelta(days=8))])
    channel = FakeChannel()
    with NudgeState(str(tmp_path / "s.db")) as state:
        run_digest(clickup=clickup, channel=channel, state=state, config=cfg(), today=TODAY)
    _, text = channel.sent[0]
    assert "🚨" in text  # urgente (8 days overdue)


def test_no_owner_chat_id_does_not_send_but_reports(tmp_path):
    clickup = FakeClickUp(tasks=_tasks())
    channel = FakeChannel()
    with NudgeState(str(tmp_path / "s.db")) as state:
        r = run_digest(clickup=clickup, channel=channel, state=state, config=cfg(owner=None), today=TODAY)
    assert r.sent is False
    assert r.count == 2
    assert channel.sent == []


def test_send_failure_does_not_mark_nudged(tmp_path):
    clickup = FakeClickUp(tasks=_tasks())
    channel = FakeChannel(fail=True)
    with NudgeState(str(tmp_path / "s.db")) as state:
        r = run_digest(clickup=clickup, channel=channel, state=state, config=cfg(), today=TODAY)
        assert r.sent is False
        # not marked -> a retry later the same day would still try
        assert state.already_nudged("a", TODAY) is False


def test_format_digest_orders_most_overdue_first():
    tasks = [
        mk("a", due_date=TODAY),
        mk("b", due_date=TODAY - timedelta(days=8)),
        mk("c", due_date=TODAY - timedelta(days=2)),
    ]
    text = format_digest(tasks, TODAY, escala_tom=True)
    lines = text.splitlines()[1:]  # drop header
    assert "task b" in lines[0]    # 8d overdue first
    assert "task c" in lines[1]    # 2d overdue next
    assert "task a" in lines[2]    # due today last

from datetime import date, timedelta

from cutuca.cadence import (
    TONE_FIRME,
    TONE_LEVE,
    TONE_NO_PRAZO,
    TONE_URGENTE,
    needs_nudge,
    select,
    tone,
)
from cutuca.config import CadenceRule
from cutuca.models import Task

TODAY = date(2026, 6, 30)


def mk(**kw) -> Task:
    base = dict(id="1", name="t", assignees=["joão"], due_date=None,
                last_update=None, status="open")
    base.update(kw)
    return Task(**base)


def test_due_today_is_nudged():
    rule = CadenceRule(vence_em_dias=0, atrasada=True, sem_update_dias=None)
    assert needs_nudge(mk(due_date=TODAY), rule, TODAY) is True


def test_due_within_window_is_nudged():
    rule = CadenceRule(vence_em_dias=2, atrasada=True, sem_update_dias=None)
    assert needs_nudge(mk(due_date=TODAY + timedelta(days=2)), rule, TODAY) is True
    assert needs_nudge(mk(due_date=TODAY + timedelta(days=3)), rule, TODAY) is False


def test_overdue_is_nudged_when_atrasada():
    rule = CadenceRule(vence_em_dias=0, atrasada=True, sem_update_dias=None)
    assert needs_nudge(mk(due_date=TODAY - timedelta(days=5)), rule, TODAY) is True


def test_overdue_ignored_when_atrasada_false():
    rule = CadenceRule(vence_em_dias=0, atrasada=False, sem_update_dias=None)
    assert needs_nudge(mk(due_date=TODAY - timedelta(days=5)), rule, TODAY) is False


def test_stale_is_nudged():
    rule = CadenceRule(vence_em_dias=None, atrasada=False, sem_update_dias=3)
    assert needs_nudge(mk(last_update=TODAY - timedelta(days=3)), rule, TODAY) is True
    assert needs_nudge(mk(last_update=TODAY - timedelta(days=2)), rule, TODAY) is False


def test_closed_never_nudged():
    rule = CadenceRule(vence_em_dias=0, atrasada=True, sem_update_dias=3)
    hopeless = mk(due_date=TODAY - timedelta(days=10), status="complete")
    assert needs_nudge(hopeless, rule, TODAY) is False
    assert needs_nudge(mk(due_date=TODAY - timedelta(days=10), status="Concluído"), rule, TODAY) is False


def test_nothing_matches():
    rule = CadenceRule(vence_em_dias=0, atrasada=True, sem_update_dias=3)
    fine = mk(due_date=TODAY + timedelta(days=10), last_update=TODAY)
    assert needs_nudge(fine, rule, TODAY) is False


def test_tone_buckets():
    assert tone(0) == TONE_NO_PRAZO
    assert tone(-3) == TONE_NO_PRAZO
    assert tone(1) == TONE_LEVE
    assert tone(2) == TONE_LEVE
    assert tone(3) == TONE_FIRME
    assert tone(6) == TONE_FIRME
    assert tone(7) == TONE_URGENTE
    assert tone(30) == TONE_URGENTE


def test_select_filters():
    rule = CadenceRule(vence_em_dias=0, atrasada=True, sem_update_dias=None)
    tasks = [
        mk(id="a", due_date=TODAY),                        # due today -> in
        mk(id="b", due_date=TODAY - timedelta(days=1)),    # overdue -> in
        mk(id="c", due_date=TODAY + timedelta(days=5)),    # future -> out
        mk(id="d", due_date=TODAY, status="done"),         # closed -> out
    ]
    got = {t.id for t in select(tasks, rule, TODAY)}
    assert got == {"a", "b"}

"""P0.2 — Severidade: fonte única no back, front só exibe (Spec §9 P0 + C11).

Severidade é por DIA de calendário (mesma régua de C11 / `tone()`): tarefa sem due é
`no_prazo`; atrasada escala leve→firme→urgente. `tone_name` deriva de `tone()` (uma só
tabela de thresholds) e aceita `None` (sem due). O modelo `Task` da API carrega os
campos estruturados `severity`/`days_overdue` para o front deixar de parsear a string
`due`.
"""
import pytest

from app.cadence import tone_name


@pytest.mark.parametrize("days,expected", [
    (None, "no_prazo"), (-3, "no_prazo"), (0, "no_prazo"),
    (1, "leve"), (2, "leve"), (3, "firme"), (6, "firme"), (7, "urgente"), (30, "urgente"),
])
def test_tone_name(days, expected):
    assert tone_name(days) == expected


def test_task_carrega_severity():
    from app.tasks import Task
    t = Task(id="1", name="x", area="Trabalho", days_overdue=4, severity=tone_name(4))
    assert t.severity == "firme"


def test_task_default_no_prazo():
    from app.tasks import Task
    t = Task(id="1", name="x", area="Trabalho")
    assert t.severity == "no_prazo" and t.days_overdue is None

"""Shared data shapes. Kept dependency-free so pure logic (cadence) never imports
network clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Task:
    """Normalized view of a ClickUp task. The adapter in ``clickup.py`` is the single
    place that maps raw API JSON into this shape, so cadence logic is insulated from
    API field drift (design decision D-3)."""

    id: str
    name: str
    assignees: list[str] = field(default_factory=list)  # display names
    due_date: Optional[date] = None
    last_update: Optional[date] = None
    status: Optional[str] = None
    url: Optional[str] = None

    def days_overdue(self, today: date) -> int:
        """Positive when past due, 0/negative otherwise. 0 when no due date."""
        if self.due_date is None:
            return 0
        return (today - self.due_date).days

    def days_until_due(self, today: date) -> Optional[int]:
        if self.due_date is None:
            return None
        return (self.due_date - today).days

    def days_since_update(self, today: date) -> Optional[int]:
        if self.last_update is None:
            return None
        return (today - self.last_update).days

"""Time conversions kept at the API boundary. ClickUp speaks epoch-milliseconds;
cutuca's logic speaks ``datetime.date`` in the owner's timezone."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


def get_tz(name: Optional[str]):
    """Return a tzinfo for a name like 'America/Sao_Paulo'; UTC if unset/invalid."""
    if not name:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def ms_to_date(ms, tz) -> Optional[date]:
    """Epoch-milliseconds (int or numeric str) -> local date. None for empty/zero."""
    if ms in (None, "", 0, "0"):
        return None
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz).date()


def iso_to_ms(iso: Optional[str], tz) -> Optional[int]:
    """'YYYY-MM-DD' -> epoch-milliseconds at local midnight. None if unparseable."""
    if not iso:
        return None
    try:
        d = date.fromisoformat(iso.strip())
    except (TypeError, ValueError):
        return None
    dt = datetime(d.year, d.month, d.day, tzinfo=tz)
    return int(dt.timestamp() * 1000)


def today_in(tz) -> date:
    return datetime.now(tz).date()

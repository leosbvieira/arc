from datetime import date

from cutuca.state import NudgeState

D1 = date(2026, 6, 30)
D2 = date(2026, 7, 1)


def test_mark_then_already(tmp_path):
    with NudgeState(str(tmp_path / "s.db")) as st:
        assert st.already_nudged("t1", D1) is False
        st.mark_nudged("t1", D1)
        assert st.already_nudged("t1", D1) is True


def test_dedupe_is_per_day(tmp_path):
    with NudgeState(str(tmp_path / "s.db")) as st:
        st.mark_nudged("t1", D1)
        assert st.already_nudged("t1", D2) is False


def test_double_mark_is_idempotent(tmp_path):
    path = str(tmp_path / "s.db")
    with NudgeState(path) as st:
        st.mark_nudged("t1", D1)
        st.mark_nudged("t1", D1)
        rows = st._conn.execute(
            "SELECT COUNT(*) FROM nudges WHERE task_id='t1' AND day=?", (D1.isoformat(),)
        ).fetchone()[0]
        assert rows == 1


def test_filter_new(tmp_path):
    with NudgeState(str(tmp_path / "s.db")) as st:
        st.mark_nudged("b", D1)
        assert st.filter_new(["a", "b", "c"], D1) == ["a", "c"]


def test_string_day_accepted(tmp_path):
    with NudgeState(str(tmp_path / "s.db")) as st:
        st.mark_nudged("t1", "2026-06-30")
        assert st.already_nudged("t1", D1) is True

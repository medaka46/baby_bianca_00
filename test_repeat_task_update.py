"""Tests for api.repeat_task_update.apply_repeat_update.

Regression: editing a repeat task's start/finish time must persist to the
repeat_start_time / repeat_end_time columns (the ones the display reads), NOT to
start_datetime / end_datetime.
"""
from datetime import date, datetime
from types import SimpleNamespace

from api.repeat_task_update import apply_repeat_update


def _repeat_row():
    return SimpleNamespace(
        is_repeat_task=1, is_daily_task=0,
        name="old", link="old", category="old", status="old",
        range_start=date(2026, 5, 1),
        start_datetime=datetime(2026, 5, 1, 0, 0),
        end_datetime=datetime(2026, 5, 1, 0, 0),
        repeat_start_time="08:00", repeat_end_time="09:00",
    )


def test_times_persist_to_repeat_columns():
    item = _repeat_row()
    apply_repeat_update(
        item, name="n", link="l", category="c", status="s",
        date1="2026-06-20", start_time="13:30", end_time="14:45",
    )
    assert item.repeat_start_time == "13:30"
    assert item.repeat_end_time == "14:45"


def test_start_end_datetime_stay_midnight_sentinel():
    item = _repeat_row()
    apply_repeat_update(
        item, name="n", link="l", category="c", status="s",
        date1="2026-06-20", start_time="13:30", end_time="14:45",
    )
    sentinel = datetime(2026, 6, 20, 0, 0)
    assert item.start_datetime == sentinel
    assert item.end_datetime == sentinel


def test_basic_fields_and_range_start_updated():
    item = _repeat_row()
    apply_repeat_update(
        item, name="n", link="l", category="c", status="s",
        date1="2026-06-20", start_time="13:30", end_time="14:45",
    )
    assert (item.name, item.link, item.category, item.status) == ("n", "l", "c", "s")
    assert item.range_start == date(2026, 6, 20)


def test_blank_times_default_to_midnight():
    item = _repeat_row()
    apply_repeat_update(
        item, name="n", link="l", category="c", status="s",
        date1="2026-06-20", start_time=None, end_time=None,
    )
    assert item.repeat_start_time == "00:00"
    assert item.repeat_end_time == "00:00"

"""Tests for api.edit_time_fields.edit_form_time_fields.

The key case is the regression: a repeat task must pre-select the times stored
in repeat_start_time / repeat_end_time, NOT a value derived from the midnight
sentinel in start_datetime (which showed as 08:00 for a UTC+8 viewer).
"""
from datetime import date, datetime
from types import SimpleNamespace

from api.edit_time_fields import edit_form_time_fields


def _daily(task_date):
    return SimpleNamespace(
        is_daily_task=1, is_repeat_task=0, task_date=task_date,
        start_datetime=None, end_datetime=None,
        repeat_start_time=None, repeat_end_time=None, range_start=None,
    )


def _repeat(repeat_start, repeat_end, range_start):
    # start/end_datetime are the midnight sentinel add_repeat_task stores.
    midnight = datetime.combine(range_start, datetime.min.time())
    return SimpleNamespace(
        is_daily_task=0, is_repeat_task=1, task_date=None,
        start_datetime=midnight, end_datetime=midnight,
        repeat_start_time=repeat_start, repeat_end_time=repeat_end,
        range_start=range_start,
    )


def _regular(start_dt, end_dt):
    return SimpleNamespace(
        is_daily_task=0, is_repeat_task=0, task_date=None,
        start_datetime=start_dt, end_datetime=end_dt,
        repeat_start_time=None, repeat_end_time=None, range_start=None,
    )


def test_repeat_task_uses_its_stored_times_not_the_sentinel():
    # The bug: this returned 08:00 in Asia/Singapore. Must return 02:00/03:00.
    item = _repeat("02:00", "03:00", date(2026, 6, 26))
    sel_date, start_t, end_t = edit_form_time_fields(item, "Asia/Singapore")
    assert (start_t, end_t) == ("02:00", "03:00")
    assert sel_date == date(2026, 6, 26)


def test_repeat_task_without_times_defaults_to_midnight():
    item = _repeat(None, None, date(2026, 5, 25))
    _, start_t, end_t = edit_form_time_fields(item, "Asia/Singapore")
    assert (start_t, end_t) == ("00:00", "00:00")


def test_daily_task_is_timeless():
    sel_date, start_t, end_t = edit_form_time_fields(_daily(date(2026, 6, 1)), "Asia/Tokyo")
    assert (sel_date, start_t, end_t) == (date(2026, 6, 1), "00:00", "00:00")


def test_regular_task_converts_utc_to_local():
    # 01:30 UTC -> 09:30 in Asia/Singapore (+08:00).
    item = _regular(datetime(2026, 6, 10, 1, 30), datetime(2026, 6, 10, 2, 45))
    sel_date, start_t, end_t = edit_form_time_fields(item, "Asia/Singapore")
    assert (start_t, end_t) == ("09:30", "10:45")
    assert sel_date == date(2026, 6, 10)

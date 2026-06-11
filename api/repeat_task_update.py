"""Persist edits to a repeat-task Schedule row from the edit form.

A repeat task keeps its time-of-day in the TZ-independent string columns
repeat_start_time / repeat_end_time; start_datetime / end_datetime hold only a
midnight sentinel tied to range_start (matching how add_repeat_task stores it).
The edit form's date field maps to range_start.
"""
from __future__ import annotations

from datetime import datetime


def apply_repeat_update(item, *, name, link, category, status, date1, start_time, end_time):
    """Mutate `item` (a repeat-task Schedule row) with edited form values."""
    d = datetime.strptime(date1, "%Y-%m-%d").date()
    item.name = name
    item.link = link
    item.category = category
    item.status = status
    item.range_start = d
    # Times are TZ-independent 'HH:MM' strings; start/end_datetime stay a
    # midnight sentinel so the calendar/edit display (which reads the repeat_*
    # columns) keeps working.
    sentinel = datetime.combine(d, datetime.min.time())
    item.start_datetime = sentinel
    item.end_datetime = sentinel
    item.repeat_start_time = start_time or "00:00"
    item.repeat_end_time = end_time or "00:00"

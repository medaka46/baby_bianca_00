"""Compute the date/time field values the schedule edit form pre-selects.

The edit form (`schedule_edit_00.html`) shows one date box and start/finish
time dropdowns. The value each control should pre-select depends on the kind of
task, and getting it wrong for repeat tasks is exactly the "always 08:00" bug:
a repeat task keeps its real time-of-day in the `repeat_start_time` /
`repeat_end_time` string columns, while `start_datetime` / `end_datetime` hold
only a midnight sentinel — converting that sentinel UTC->local yields a bogus
time (e.g. 08:00 in UTC+8).
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd


def edit_form_time_fields(item, time_zone: str):
    """Return (selected_date, selected_start_time, selected_end_time).

    `selected_date` is a date object; the two times are 'HH:MM' strings.
    """
    if item.is_daily_task:
        # Daily task: date is TZ-independent, no time component.
        return item.task_date, "00:00", "00:00"

    if item.is_repeat_task:
        # Repeat task: time-of-day lives in the dedicated 'HH:MM' columns and is
        # TZ-independent. start_datetime/end_datetime hold only a midnight
        # sentinel, so converting them would mis-report the time (08:00 in UTC+8).
        return (
            item.range_start,
            item.repeat_start_time or "00:00",
            item.repeat_end_time or "00:00",
        )

    # Regular task: convert the stored UTC datetimes to the viewer's local time.
    utc_start_datetime = pd.Timestamp(item.start_datetime).tz_localize("UTC")
    utc_end_datetime = pd.Timestamp(item.end_datetime).tz_localize("UTC")
    local_start_datetime = utc_start_datetime.astimezone(ZoneInfo(time_zone))
    local_end_datetime = utc_end_datetime.astimezone(ZoneInfo(time_zone))
    return (
        local_start_datetime.date(),
        local_start_datetime.time().strftime("%H:%M"),
        local_end_datetime.time().strftime("%H:%M"),
    )

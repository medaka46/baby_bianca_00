"""Expand a Schedule template row (is_repeat_task=1) into virtual per-date dicts
that match the daily-task render shape consumed by schedule_indicate_00.html.

Pure functions only — no DB or HTTP — so this can be smoke-checked in a REPL.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable


def parse_weekdays_csv(csv: str | None) -> set[int]:
    """'0,2,4' -> {0, 2, 4}.  Empty / None -> empty set."""
    if not csv:
        return set()
    out: set[int] = set()
    for part in csv.split(","):
        part = part.strip()
        if part.isdigit():
            n = int(part)
            if 0 <= n <= 6:
                out.add(n)
    return out


def date_matches_template(
    d: date,
    repeat_type: str,
    weekdays: set[int],
    range_start: date | None,
    range_end: date | None,
) -> bool:
    if range_start and d < range_start:
        return False
    if range_end and d > range_end:
        return False
    if repeat_type == "every_day":
        return True
    if repeat_type == "every_weekday":
        return d.weekday() < 5  # Mon=0 … Fri=4
    if repeat_type == "every_specific_weekday":
        return d.weekday() in weekdays
    return False


def expand_template(row, visible_dates: Iterable[str], today: str | None = None) -> list[dict]:
    """Return one virtual dict per visible date the template matches.

    `row` is a SQLAlchemy Schedule row (or any object with the same attribute
    names). `visible_dates` is the date_sequence already built by the caller —
    we only emit occurrences within the window the UI actually renders.

    `today` is the caller's local-TZ today as ISO 'YYYY-MM-DD'. When the row's
    `today_only` flag is set, only that date is emitted (and only if the
    repeat pattern matches it).
    """
    weekdays = parse_weekdays_csv(row.repeat_weekdays)
    today_only = bool(getattr(row, "today_only", 0))
    # Time-of-day (TZ-independent). Treat blank / 00:00 sentinel as "no time".
    start_t = getattr(row, "repeat_start_time", None) or ""
    end_t = getattr(row, "repeat_end_time", None) or ""
    if start_t in ("", "00:00") and end_t in ("", "00:00"):
        start_t = end_t = ""
    out: list[dict] = []
    for iso in visible_dates:
        if today_only and iso != today:
            continue
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        if not date_matches_template(
            d, row.repeat_type or "", weekdays, row.range_start, row.range_end
        ):
            continue
        out.append({
            "id": row.id,
            "name": row.name,
            "link": row.link,
            "start_datetime": None,
            "end_datetime": None,
            "local_start_date": iso,
            "local_start_time": start_t,
            "local_end_date": iso,
            "local_end_time": end_t,
            "is_daily_task": 1,        # render with the 🟩 prefix
            "is_repeat_task": 1,       # for future code that needs to distinguish
            "today_only": 1 if today_only else 0,
        })
    return out

"""One-off migration: add is_daily_task / task_date to the schedules table,
then convert legacy 00:01-sentinel rows (the old WFH / NH-in-Philippines style)
into proper daily-task rows.

Run once, locally and on Render.

  Local:   python -m scripts.migrate_daily_tasks
  Render:  Shell tab → python -m scripts.migrate_daily_tasks

Idempotent: re-running is safe (each step is guarded).

Why Asia/Manila for date recovery:
  Sentinel rows were stored as `local 00:01` in the creator's TZ, then converted
  to UTC. The creator's TZ isn't recorded on the row, so we cannot perfectly
  recover the original calendar date for every row. The project owner works in
  Manila, so Asia/Manila is the right default. If you created any sentinel
  rows from another TZ, edit them manually after migration.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# Allow running as `python -m scripts.migrate_daily_tasks` from project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import get_database_path  # noqa: E402

CREATOR_TZ = ZoneInfo("Asia/Manila")


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def add_columns(conn: sqlite3.Connection) -> None:
    if not column_exists(conn, "schedules", "is_daily_task"):
        conn.execute("ALTER TABLE schedules ADD COLUMN is_daily_task INTEGER DEFAULT 0")
        print("  + added column schedules.is_daily_task")
    else:
        print("  = column schedules.is_daily_task already exists")
    if not column_exists(conn, "schedules", "task_date"):
        conn.execute("ALTER TABLE schedules ADD COLUMN task_date DATE")
        print("  + added column schedules.task_date")
    else:
        print("  = column schedules.task_date already exists")


def convert_sentinel_rows(conn: sqlite3.Connection) -> int:
    """Find rows where start_datetime == end_datetime (the old daily-task sentinel)
    and not already migrated. Set is_daily_task=1, task_date=<creator-TZ date>.

    start_datetime / end_datetime are NOT NULL in this table (legacy schema),
    so we cannot null them out. Instead we normalise both to UTC midnight of
    task_date — that value is never used for display when is_daily_task=1, but
    keeps ORDER BY start_datetime stable and satisfies the constraint.
    """
    rows = conn.execute(
        "SELECT id, start_datetime, end_datetime "
        "FROM schedules "
        "WHERE (is_daily_task IS NULL OR is_daily_task = 0) "
        "  AND start_datetime IS NOT NULL "
        "  AND end_datetime IS NOT NULL "
        "  AND start_datetime = end_datetime"
    ).fetchall()

    migrated = 0
    for row_id, start_str, _end_str in rows:
        try:
            utc_dt = datetime.fromisoformat(str(start_str)).replace(tzinfo=ZoneInfo("UTC"))
        except ValueError:
            print(f"  ! row id={row_id}: cannot parse start_datetime={start_str!r}, skipped")
            continue
        local_dt = utc_dt.astimezone(CREATOR_TZ)
        task_date_iso = local_dt.date().isoformat()
        sentinel_dt = f"{task_date_iso} 00:00:00"
        conn.execute(
            "UPDATE schedules SET is_daily_task = 1, task_date = ?, "
            "start_datetime = ?, end_datetime = ? WHERE id = ?",
            (task_date_iso, sentinel_dt, sentinel_dt, row_id),
        )
        migrated += 1
    return migrated


def main() -> None:
    db_path = get_database_path()
    print(f"Migrating database at: {db_path}")
    if not os.path.exists(db_path):
        print("Database file does not exist — nothing to migrate.")
        return
    conn = sqlite3.connect(db_path)
    try:
        add_columns(conn)
        n = convert_sentinel_rows(conn)
        conn.commit()
        print(f"Converted {n} sentinel row(s) to daily tasks.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

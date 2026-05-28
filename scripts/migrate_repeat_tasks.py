"""One-off migration: add repeat-task columns to the schedules table.

Adds six columns used by the Repeat Task feature:
  is_repeat_task   INTEGER DEFAULT 0
  repeat_type      TEXT       -- 'every_day' | 'every_weekday' | 'every_specific_weekday'
  repeat_weekdays  TEXT       -- CSV of Python weekday ints, e.g. '0,2,4' (Mon=0..Sun=6)
  range_start      DATE
  range_end        DATE
  today_only       INTEGER DEFAULT 0  -- 1 = show occurrence only in Today area

Run once, locally and on Render.

  Local:   python -m scripts.migrate_repeat_tasks
  Render:  Shell tab -> python -m scripts.migrate_repeat_tasks

Idempotent: re-running is safe (each column add is guarded).
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import get_database_path  # noqa: E402


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def add_columns(conn: sqlite3.Connection) -> None:
    specs = [
        ("is_repeat_task", "INTEGER DEFAULT 0"),
        ("repeat_type", "TEXT"),
        ("repeat_weekdays", "TEXT"),
        ("range_start", "DATE"),
        ("range_end", "DATE"),
        ("today_only", "INTEGER DEFAULT 0"),
    ]
    for name, sql_type in specs:
        if not column_exists(conn, "schedules", name):
            conn.execute(f"ALTER TABLE schedules ADD COLUMN {name} {sql_type}")
            print(f"  + added column schedules.{name}")
        else:
            print(f"  = column schedules.{name} already exists")


def main() -> None:
    db_path = get_database_path()
    print(f"Migrating database at: {db_path}")
    if not os.path.exists(db_path):
        print("Database file does not exist - nothing to migrate.")
        return
    conn = sqlite3.connect(db_path)
    try:
        add_columns(conn)
        conn.commit()
        print("Repeat-task columns migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

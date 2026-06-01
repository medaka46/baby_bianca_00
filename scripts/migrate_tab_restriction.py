"""One-off migration: user tab restriction.

1. Adds column  users.tab_group TEXT
2. Creates table tab_group(id, group_key UNIQUE, group_name, tab_keys)
3. Seeds group 'a' = ALL tabs, and sets user 'a'.tab_group = 'a'
   so the existing user 'a' keeps full access (per agreed requirement).

Run once, locally and on Render.
  Local:   python -m scripts.migrate_tab_restriction
  Render:  Shell tab -> python -m scripts.migrate_tab_restriction

Idempotent: re-running is safe (each step is guarded).
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import get_database_path  # noqa: E402

ALL_TABS = "schedule,link_00,project,action,todo,diary,3d,music,game,sqlite"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def migrate(conn: sqlite3.Connection) -> None:
    # 1. users.tab_group
    if not column_exists(conn, "users", "tab_group"):
        conn.execute("ALTER TABLE users ADD COLUMN tab_group VARCHAR")
        print("  + added column users.tab_group")
    else:
        print("  = column users.tab_group already exists")

    # 2. tab_group table
    if not table_exists(conn, "tab_group"):
        conn.execute(
            "CREATE TABLE tab_group ("
            "id INTEGER PRIMARY KEY, "
            "group_key VARCHAR, "
            "group_name VARCHAR, "
            "tab_keys VARCHAR)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX ix_tab_group_group_key "
            "ON tab_group (group_key)"
        )
        print("  + created table tab_group")
    else:
        print("  = table tab_group already exists")

    # 3. seed group 'a' = all tabs
    row = conn.execute(
        "SELECT id FROM tab_group WHERE group_key = 'a'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO tab_group (group_key, group_name, tab_keys) "
            "VALUES ('a', 'Full access', ?)",
            (ALL_TABS,),
        )
        print("  + seeded tab_group 'a' (Full access = all tabs)")
    else:
        # keep it current with the full tab list
        conn.execute(
            "UPDATE tab_group SET tab_keys = ? WHERE group_key = 'a'",
            (ALL_TABS,),
        )
        print("  = tab_group 'a' already exists (refreshed tab_keys)")

    # 4. assign user 'a' -> group 'a'
    result = conn.execute(
        "UPDATE users SET tab_group = 'a' WHERE username = 'a'"
    )
    print(f"  = set tab_group='a' for {result.rowcount} user row(s) named 'a'")


def main() -> None:
    db_path = get_database_path()
    print(f"Migrating database at: {db_path}")
    if not os.path.exists(db_path):
        print("Database file does not exist - nothing to migrate.")
        return
    conn = sqlite3.connect(db_path)
    try:
        migrate(conn)
        conn.commit()
        print("Tab-restriction migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

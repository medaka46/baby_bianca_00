"""One-off migration: add allowed_users.tab_group.

When an admin pre-approves a sign-up (allowed_users row), they also choose the
tab_group the new account will inherit at registration time. This avoids the
broken first-login experience where a freshly registered user has no tabs until
an admin assigns a group manually.

No data seeding — the column is added nullable; existing rows keep NULL (the new
account would start with no tabs, same as before this change).

Run once, locally and on Render.
  Local:   python -m scripts.migrate_allowed_user_group
  Render:  Shell tab -> python -m scripts.migrate_allowed_user_group

Idempotent: re-running is safe (the column add is guarded).
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


def migrate(conn: sqlite3.Connection) -> None:
    if not column_exists(conn, "allowed_users", "tab_group"):
        conn.execute("ALTER TABLE allowed_users ADD COLUMN tab_group VARCHAR")
        print("  + added column allowed_users.tab_group")
    else:
        print("  = column allowed_users.tab_group already exists")


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
        print("Allowed-user-group migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

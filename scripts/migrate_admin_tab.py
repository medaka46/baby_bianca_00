"""One-off migration: grant the 'admin' tab to the full-access group 'a'.

The Admin tab is gated by the canonical tab key 'admin' (see api/admin.py and
templates/base.html). This script idempotently ensures group 'a' (Full access)
has 'admin' in its tab_keys, so the existing admin user keeps access to the new
Admin tab without hand-editing the database.

No schema change (no new tables/columns) — 'admin' is just another value in the
existing tab_group.tab_keys CSV.

Run once, locally and on Render.
  Local:   python -m scripts.migrate_admin_tab
  Render:  Shell tab -> python -m scripts.migrate_admin_tab

Idempotent: re-running is safe.
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import get_database_path  # noqa: E402


def add_admin_to_group_a(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT tab_keys FROM tab_group WHERE group_key = 'a'"
    ).fetchone()
    if row is None:
        print("  ! group 'a' not found - run migrate_tab_restriction first.")
        return
    keys = [k.strip() for k in (row[0] or "").split(",") if k.strip()]
    if "admin" in keys:
        print("  = group 'a' already has 'admin'")
        return
    keys.append("admin")
    new_csv = ",".join(keys)
    conn.execute(
        "UPDATE tab_group SET tab_keys = ? WHERE group_key = 'a'",
        (new_csv,),
    )
    print(f"  + added 'admin' to group 'a' (tab_keys = {new_csv})")


def main() -> None:
    db_path = get_database_path()
    print(f"Migrating database at: {db_path}")
    if not os.path.exists(db_path):
        print("Database file does not exist - nothing to migrate.")
        return
    conn = sqlite3.connect(db_path)
    try:
        add_admin_to_group_a(conn)
        conn.commit()
        print("Admin-tab migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""Startup schema guard.

Turns a cryptic runtime 500 ("no such column: users.tab_group") into a loud,
actionable message — at startup in the logs, and on screen via an exception
handler — when the deployed database is missing schema added by a migration
that has not been run yet.

Why this exists: Render does NOT auto-apply render.yaml startCommand changes, so
after a schema-change deploy the migration must be run manually in the Render
Shell. SQLAlchemy's Base.metadata.create_all() papers over MISSING TABLES but
never ALTERs an existing table to add a MISSING COLUMN — so the tab_group
columns are exactly what silently goes missing and crashes every authenticated
page through permissions.allowed_tabs_for().
"""
from __future__ import annotations

import os
import sqlite3

# Columns required by the tab-restriction / admin-tab work, paired with the
# migration that adds each. Checked individually because create_all() cannot
# add a column to an already-existing table.
REQUIRED_COLUMNS = [
    ("users", "tab_group", "scripts.migrate_tab_restriction"),
    ("allowed_users", "tab_group", "scripts.migrate_allowed_user_group"),
]

# Tables required by the same work. (create_all() usually recreates these, so
# this rarely fires, but it keeps the guard complete.)
REQUIRED_TABLES = [
    ("tab_group", "scripts.migrate_admin_tab"),
]

# The full idempotent chain to run once in the Render Shell.
MIGRATION_COMMAND = (
    "python -m scripts.migrate_daily_tasks && "
    "python -m scripts.migrate_repeat_tasks && "
    "python -m scripts.migrate_tab_restriction && "
    "python -m scripts.migrate_admin_tab && "
    "python -m scripts.migrate_allowed_user_group"
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def missing_schema(db_path: str) -> list[str]:
    """Return human-readable descriptions of missing schema items.

    Empty list means the schema is up to date. A non-existent DB file returns an
    empty list (a brand-new deploy will have its tables created on first run).
    """
    if not os.path.exists(db_path):
        return []
    missing: list[str] = []
    conn = sqlite3.connect(db_path)
    try:
        for table, mig in REQUIRED_TABLES:
            if not _table_exists(conn, table):
                missing.append(f"table '{table}'  (run: {mig})")
        for table, column, mig in REQUIRED_COLUMNS:
            if not _column_exists(conn, table, column):
                missing.append(f"column '{table}.{column}'  (run: {mig})")
    finally:
        conn.close()
    return missing


def format_warning(missing: list[str]) -> str:
    """Build the prominent multi-line log message for a stale schema."""
    bar = "!" * 72
    lines = [
        bar,
        "DATABASE SCHEMA OUT OF DATE — the app will error until migrations run.",
        "Missing:",
    ]
    lines += [f"    - {m}" for m in missing]
    lines += [
        "Run this once in the Render Shell (idempotent, safe to re-run):",
        f"    {MIGRATION_COMMAND}",
        bar,
    ]
    return "\n".join(lines)


def is_missing_schema_error(message: str) -> bool:
    """True if a sqlite OperationalError message looks like a stale-schema crash."""
    msg = message.lower()
    return "no such column" in msg or "no such table" in msg

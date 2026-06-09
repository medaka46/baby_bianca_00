"""Tests for api.schema_check — the startup migration guard.

These verify that a DB missing the tab-restriction columns is detected, that an
up-to-date DB reports nothing missing, and that the warning message names the
exact migration command to run.
"""
import sqlite3

from api.schema_check import missing_schema, format_warning, MIGRATION_COMMAND


def _make_db(path, *, with_user_group, with_allowed_group, with_tab_group_table):
    conn = sqlite3.connect(path)
    user_cols = "id INTEGER PRIMARY KEY, username TEXT"
    if with_user_group:
        user_cols += ", tab_group TEXT"
    conn.execute(f"CREATE TABLE users ({user_cols})")

    allowed_cols = "id INTEGER PRIMARY KEY, username TEXT"
    if with_allowed_group:
        allowed_cols += ", tab_group TEXT"
    conn.execute(f"CREATE TABLE allowed_users ({allowed_cols})")

    if with_tab_group_table:
        conn.execute("CREATE TABLE tab_group (id INTEGER PRIMARY KEY, group_key TEXT)")
    conn.commit()
    conn.close()


def test_fully_migrated_db_reports_nothing(tmp_path):
    db = tmp_path / "ok.db"
    _make_db(db, with_user_group=True, with_allowed_group=True, with_tab_group_table=True)
    assert missing_schema(str(db)) == []


def test_missing_users_tab_group_is_detected(tmp_path):
    db = tmp_path / "stale.db"
    _make_db(db, with_user_group=False, with_allowed_group=True, with_tab_group_table=True)
    missing = missing_schema(str(db))
    assert any("users.tab_group" in m for m in missing)


def test_missing_allowed_users_tab_group_is_detected(tmp_path):
    db = tmp_path / "stale2.db"
    _make_db(db, with_user_group=True, with_allowed_group=False, with_tab_group_table=True)
    missing = missing_schema(str(db))
    assert any("allowed_users.tab_group" in m for m in missing)


def test_missing_tab_group_table_is_detected(tmp_path):
    db = tmp_path / "stale3.db"
    _make_db(db, with_user_group=True, with_allowed_group=True, with_tab_group_table=False)
    missing = missing_schema(str(db))
    assert any("tab_group" in m for m in missing)


def test_nonexistent_db_file_reports_no_false_positive(tmp_path):
    # A brand-new deploy with no DB yet should not crash the check.
    db = tmp_path / "does_not_exist.db"
    assert missing_schema(str(db)) == []


def test_warning_message_names_the_migration_command(tmp_path):
    db = tmp_path / "stale4.db"
    _make_db(db, with_user_group=False, with_allowed_group=False, with_tab_group_table=True)
    text = format_warning(missing_schema(str(db)))
    assert MIGRATION_COMMAND in text
    assert "users.tab_group" in text

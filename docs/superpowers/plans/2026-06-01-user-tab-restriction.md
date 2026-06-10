# User Tab Restriction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict which top-bar tabs each user can see and reach, driven by a per-user `tab_group` and a `tab_group` table that lists allowed tabs per group; default is no access (no group → no tabs).

**Architecture:** Add a `tab_group` column to `users` and a new `tab_group` table (`group_key`, `group_name`, `tab_keys` CSV). A single helper resolves the logged-in user → group → allowed-tab set. Two enforcement layers use that helper: (1) `base.html` hides the buttons for tabs not allowed, (2) each tab route redirects to a "no access" page when the tab is not allowed. Default behavior: a user with no/empty `tab_group`, or no matching group, gets an empty allowed set (sees nothing).

**Tech Stack:** FastAPI, SQLAlchemy (SQLite `test.db`), Jinja2 templates, Starlette `SessionMiddleware` (session key `login_username`). Render persistent disk requires a manual migration run.

**Testing note (codebase reality):** This repo has no test framework (no `tests/`, no pytest). The established verification pattern (per `HANDOFF_CODY_TO_CLAUDY.md`) is `python -m compileall` + manual browser testing. This plan follows that pattern and adds one tiny self-contained `assert` script for the single piece of pure logic (CSV parsing). It deliberately does NOT introduce pytest.

**Canonical tab keys** (must match `tab_page_active` values already used in `templates/base.html`):
`schedule, link_00, project, action, todo, diary, 3d, music, game, sqlite`
ALL_TABS string = `"schedule,link_00,project,action,todo,diary,3d,music,game,sqlite"`

| Tab key   | Button label | Landing route |
|-----------|--------------|---------------|
| schedule  | Schedule     | `/schedule/`  |
| link_00   | Link         | `/link_00/`   |
| project   | Project      | `/project/`   |
| action    | Function     | `/action/`    |
| todo      | To Do        | `/todo/`      |
| diary     | Diary/Memo   | `/diary/`     |
| 3d        | 3D Viewer    | `/3d/`        |
| music     | Music        | `/music/`     |
| game      | Game         | `/game/`      |
| sqlite    | Data         | `/sqlite/`    |

---

## File Structure

- `api/models.py` — add `tab_group` column to `User`; add new `TabGroup` model.
- `scripts/migrate_tab_restriction.py` — **new**: idempotent migration that (a) adds `users.tab_group`, (b) creates `tab_group` table, (c) seeds group `'a'` = all tabs and sets user `a`'s `tab_group = 'a'`.
- `api/permissions.py` — **new**: pure helper `parse_tab_keys(csv)` and resolver `allowed_tabs_for(request)` + `tab_guard(request, tab_key)`.
- `api/main.py` — register `allowed_tabs_for` as a Jinja global on the final `templates` object; add guards at the top of each tab landing route; add a `/no_access/` route.
- `templates/base.html` — compute allowed set once, wrap each tab `<form>` in an `{% if %}`.
- `templates/no_access.html` — **new**: small message page for users with no allowed tabs.
- `scripts/check_tab_permissions.py` — **new**: standalone assert check for `parse_tab_keys`.
- `render.yaml` — add `python -m scripts.migrate_tab_restriction` to `startCommand` (documentation/parity only; Render still requires manual run per project rule).

---

## Task 1: Database schema — model definitions

**Files:**
- Modify: `api/models.py`

- [ ] **Step 1: Add `tab_group` column to the `User` model**

In `api/models.py`, inside `class User(Base)`, add the column after `password`:

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, Sequence('user_id_seq'), primary_key=True, index=True)
    username = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    # tab_group: which permission group this user belongs to (e.g. 'a').
    # NULL/empty means the user is allowed NO tabs (default deny).
    tab_group = Column(String, index=True)
```

- [ ] **Step 2: Add the `TabGroup` model**

Add a new model below `AllowedUser` in `api/models.py`:

```python
class TabGroup(Base):
    """Defines, per group, which top-bar tabs are allowed.

    group_key : short id stored on users.tab_group, e.g. 'a', 'b', 'c'.
    group_name: optional human label, e.g. 'Full access', 'Site staff'.
    tab_keys  : CSV of allowed tab keys, using the same identifiers as
                tab_page_active in templates/base.html, e.g.
                'schedule,project,todo'. Empty means no tabs.
    """
    __tablename__ = "tab_group"
    id = Column(Integer, Sequence('tab_group_id_seq'), primary_key=True, index=True)
    group_key = Column(String, unique=True, index=True)
    group_name = Column(String)
    tab_keys = Column(String)
```

- [ ] **Step 3: Verify the module imports cleanly**

Run: `python -m compileall api/models.py`
Expected: `Compiling 'api/models.py'...` with no error, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add api/models.py
git commit -m "models: add users.tab_group column and TabGroup table"
```

---

## Task 2: Pure permission helpers + self-contained check

**Files:**
- Create: `api/permissions.py`
- Create: `scripts/check_tab_permissions.py`

- [ ] **Step 1: Write the standalone assert check first (drives the parser API)**

Create `scripts/check_tab_permissions.py`:

```python
"""Standalone check for tab-permission parsing logic.

No pytest needed. Run:  python -m scripts.check_tab_permissions
Exits 0 on success, prints FAIL and exits 1 on any failed assertion.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.permissions import parse_tab_keys  # noqa: E402


def main() -> None:
    # Normal CSV
    assert parse_tab_keys("schedule,project") == {"schedule", "project"}
    # Whitespace and blanks are tolerated
    assert parse_tab_keys(" schedule , , project ") == {"schedule", "project"}
    # Empty / None means NO tabs (default deny)
    assert parse_tab_keys("") == set()
    assert parse_tab_keys(None) == set()
    # Single tab
    assert parse_tab_keys("sqlite") == {"sqlite"}
    print("check_tab_permissions: all assertions passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the check to verify it fails (module does not exist yet)**

Run: `python -m scripts.check_tab_permissions`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.permissions'`.

- [ ] **Step 3: Implement `api/permissions.py`**

Create `api/permissions.py`:

```python
"""Tab-permission resolution for the multi-user tab restriction feature.

Resolution chain:
  session login_username -> users.tab_group -> tab_group.tab_keys (CSV) -> set

Default deny: missing username, missing/empty tab_group, missing group row,
or empty tab_keys all resolve to an empty set (the user sees no tabs).
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from api.database import SessionLocal
from api.models import User, TabGroup


def parse_tab_keys(csv: str | None) -> set[str]:
    """Parse a tab_keys CSV into a set, tolerating spaces and blanks."""
    if not csv:
        return set()
    return {part.strip() for part in csv.split(",") if part.strip()}


def allowed_tabs_for(request: Request) -> set[str]:
    """Return the set of tab keys the current session user may access."""
    login_username = request.session.get("login_username")
    if not login_username:
        return set()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == login_username).first()
        if not user or not user.tab_group:
            return set()
        group = db.query(TabGroup).filter(
            TabGroup.group_key == user.tab_group
        ).first()
        if not group:
            return set()
        return parse_tab_keys(group.tab_keys)
    finally:
        db.close()


def tab_guard(request: Request, tab_key: str):
    """Return a redirect to /no_access/ if tab_key is not allowed, else None."""
    if tab_key in allowed_tabs_for(request):
        return None
    return RedirectResponse(url="/no_access/", status_code=303)
```

- [ ] **Step 4: Run the check to verify it passes**

Run: `python -m scripts.check_tab_permissions`
Expected: `check_tab_permissions: all assertions passed.` (exit code 0)

- [ ] **Step 5: Verify compile**

Run: `python -m compileall api/permissions.py scripts/check_tab_permissions.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add api/permissions.py scripts/check_tab_permissions.py
git commit -m "permissions: add tab-permission resolver and standalone check"
```

---

## Task 3: Migration script (schema + seed group 'a' = all tabs)

**Files:**
- Create: `scripts/migrate_tab_restriction.py`

- [ ] **Step 1: Write the migration script**

Create `scripts/migrate_tab_restriction.py` (modeled on `scripts/migrate_repeat_tasks.py`, idempotent):

```python
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
```

- [ ] **Step 2: Back up the local DB before running (safety)**

Run:
```bash
cp test.db test_backup_before_tab_restriction.db
```
Expected: backup file created (mirrors existing `test_backup_*` convention).

- [ ] **Step 3: Run the migration locally**

Run: `python -m scripts.migrate_tab_restriction`
Expected output includes:
```
  + added column users.tab_group
  + created table tab_group
  + seeded tab_group 'a' (Full access = all tabs)
  = set tab_group='a' for 1 user row(s) named 'a'
Tab-restriction migration complete.
```

- [ ] **Step 4: Verify the data in SQLite**

Run:
```bash
sqlite3 test.db "SELECT username, tab_group FROM users; SELECT group_key, tab_keys FROM tab_group;"
```
Expected: user `a` shows `tab_group = a`; `michiba` and `tanaka` show empty/NULL; `tab_group` table has row `a | schedule,link_00,project,action,todo,diary,3d,music,game,sqlite`.

- [ ] **Step 5: Verify idempotency**

Run again: `python -m scripts.migrate_tab_restriction`
Expected: lines now show `= column ... already exists`, `= table ... already exists`, `= tab_group 'a' already exists (refreshed tab_keys)`. No error.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_tab_restriction.py
git commit -m "scripts: add idempotent tab-restriction migration (seed group a = all tabs)"
```

> NOTE: `test.db` itself is committed in this repo; staging it is optional and follows your usual habit. The migration is also re-runnable on Render against the persistent-disk DB.

---

## Task 4: Backend enforcement — guards on tab landing routes + /no_access/

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Import the helpers in `api/main.py`**

Near the other `from api...` imports at the top of `api/main.py`, add:

```python
from api.permissions import allowed_tabs_for, tab_guard
```

- [ ] **Step 2: Register the Jinja global on the FINAL `templates` object**

`api/main.py` defines `templates` twice (around line 34 and again around line 51); the second definition wins. Immediately AFTER the second `templates = Jinja2Templates(directory="templates")` line, add:

```python
# Make the allowed-tab resolver callable from templates (base.html).
templates.env.globals["allowed_tabs_for"] = allowed_tabs_for
```

- [ ] **Step 3: Add the `/no_access/` route**

Add this route in `api/main.py` (place it near the other simple GET routes, e.g. just above `@app.get("/sqlite/")`):

```python
@app.get("/no_access/")
async def no_access(request: Request):
    login_username = request.session.get('login_username')
    return templates.TemplateResponse("no_access.html", {
        "request": request,
        "login_username": login_username,
        "time_zone": request.session.get('time_zone'),
        "tab_page_active": "",
        "today": today_in_session_tz(request),
    })
```

- [ ] **Step 4: Add a guard to each of the 10 tab landing routes**

For each landing route below, insert the guard as the **first two statements inside the function body** (immediately after the existing `login_username = request.session.get('login_username')` line). Use the matching `tab_key`:

`/schedule/` (line ~733) → `"schedule"`
`/link_00/` (line ~1483) → `"link_00"`
`/project/` (line ~2025) → `"project"`
`/action/` (line ~1867) → `"action"`
`/todo/` (line ~2176) → `"todo"`
`/diary/` (line ~2392) → `"diary"`
`/3d/` (line ~1971) → `"3d"`
`/music/` (line ~1789) → `"music"`
`/game/` (line ~1983) → `"game"`
`/sqlite/` (line ~1958) → `"sqlite"`

Guard snippet (example for `/sqlite/`):

```python
@app.get("/sqlite/")
async def sqlite_page(request: Request):
    login_username = request.session.get('login_username')
    guard = tab_guard(request, "sqlite")
    if guard:
        return guard
    time_zone = request.session.get('time_zone')
    return templates.TemplateResponse("sqlite_00.html", {
        ...
    })
```

Apply the same two-line guard (with the route's own `tab_key`) to all ten landing routes. Do NOT change any other logic in those routes.

> Note on sub-routes: deeper routes (e.g. `/music/start_download/`, `/sqlite/...`, `/action/map/`) are reachable only after the landing page in normal use. Guarding the 10 landing routes covers the agreed scope. Guarding sub-routes can be a later hardening pass; list it under Follow-Up rather than expanding this task.

- [ ] **Step 5: Verify compile**

Run: `python -m compileall api/main.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add api/main.py
git commit -m "main: enforce tab restriction on landing routes + add /no_access/"
```

---

## Task 5: Frontend — hide disallowed tab buttons in base.html

**Files:**
- Modify: `templates/base.html`
- Create: `templates/no_access.html`

- [ ] **Step 1: Compute the allowed set once, at the top of the tab bar**

In `templates/base.html`, immediately after `<div style="display: flex;">` (around line 518, before the first `<form action="/schedule/">`), add:

```html
{% set allowed_tabs = allowed_tabs_for(request) %}
```

- [ ] **Step 2: Wrap each tab form in an `{% if %}`**

Wrap each of the ten tab `<form>...</form>` blocks so it only renders when allowed. Example for Schedule and Data; apply the same pattern to all ten:

```html
{% if "schedule" in allowed_tabs %}
<form action="/schedule/" method="get">
    <button type="submit" style="background-color: #444; color: {{ "#0f0" if tab_page_active == "schedule" else "#aaa" }};">Schedule</button>
</form>
{% endif %}
```

```html
{% if "sqlite" in allowed_tabs %}
<form action="/sqlite/" method="get">
    <button type="submit" style="background-color: #444; color: {{ "#f00" if tab_page_active == "sqlite" else "#aaa" }};">Data</button>
</form>
{% endif %}
```

Map of `{% if %}` keys to the existing forms:
`"schedule"` → Schedule form; `"link_00"` → Link form; `"project"` → Project form; `"action"` → Function form; `"todo"` → To Do form; `"diary"` → Diary/Memo form; `"3d"` → 3D Viewer form; `"music"` → Music form; `"game"` → Game form; `"sqlite"` → Data form.

Do NOT wrap the time-zone `<form action="/schedule/select_time_zone/">` block — it is not a tab and must remain visible.

- [ ] **Step 3: Create the no-access page**

Create `templates/no_access.html`:

```html
{% extends "base.html" %}
{% block content %}
<div style="color: #ccc; padding: 40px; font-family: sans-serif;">
    <h2 style="color: #0f0;">No tabs are assigned to your account</h2>
    <p>Your account{% if login_username %} (<strong>{{ login_username }}</strong>){% endif %}
       currently has no accessible tabs.</p>
    <p>Please contact the administrator to be assigned a tab group.</p>
</div>
{% endblock %}
```

> Before finalizing this file: confirm `base.html` actually defines a `{% block content %}`. If `base.html` uses a different block name (or none), match whatever the other page templates (e.g. `sqlite_00.html`) use to extend it, so `no_access.html` renders inside the same frame. Adjust the block name accordingly — do not invent one.

- [ ] **Step 4: Verify templates render (manual, app running)**

Start the app:
```bash
.py31205/bin/python -m uvicorn api.main:app --reload
```
(Use the project interpreter `.py31205` per project rules; adjust the path if needed.)

- [ ] **Step 5: Commit**

```bash
git add templates/base.html templates/no_access.html
git commit -m "base.html: hide disallowed tabs; add no_access page"
```

---

## Task 6: End-to-end manual verification

**Files:** none (manual testing)

- [ ] **Step 1: Log in as user `a` — full access**

Log in as `a`. Expected: ALL ten tabs visible. Click each tab; each loads its page (no redirect to `/no_access/`).

- [ ] **Step 2: Log in as `michiba` — default deny**

Log in as `michiba` (no `tab_group`). Expected: NO tabs in the bar (only the time-zone selector remains). Manually type a tab URL, e.g. `http://localhost:8000/sqlite/`. Expected: redirected to `/no_access/`, showing the "No tabs are assigned" message.

- [ ] **Step 3: Partial group check**

Manually create a limited group and assign `michiba` to it:
```bash
sqlite3 test.db "INSERT INTO tab_group (group_key, group_name, tab_keys) VALUES ('b','Limited','schedule,todo'); UPDATE users SET tab_group='b' WHERE username='michiba';"
```
Re-login as `michiba`. Expected: only **Schedule** and **To Do** tabs visible; visiting `/sqlite/` still redirects to `/no_access/`; visiting `/schedule/` works.

- [ ] **Step 4: Clean up the temporary test group (optional)**

```bash
sqlite3 test.db "UPDATE users SET tab_group=NULL WHERE username='michiba'; DELETE FROM tab_group WHERE group_key='b';"
```

- [ ] **Step 5: Final compile sanity**

Run: `python -m compileall api scripts`
Expected: no errors.

---

## Task 7: Render deployment notes (no code execution here)

**Files:**
- Modify: `render.yaml` (optional, for parity/documentation)

- [ ] **Step 1: Add migration to startCommand for documentation/parity**

In `render.yaml`, extend `startCommand` to include the new migration (matches the existing chain):

```
startCommand: python -m scripts.migrate_daily_tasks && python -m scripts.migrate_repeat_tasks && python -m scripts.migrate_tab_restriction && uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 2: Document the manual Render step**

Per project rule (`project_render_migrations`): Render does NOT auto-apply `render.yaml` startCommand changes. After pushing, open the Render **Shell** and run:
```
python -m scripts.migrate_tab_restriction
```
Then assign groups to the production users (`a` is already handled by the seed; assign others as desired).

- [ ] **Step 3: Commit**

```bash
git add render.yaml
git commit -m "render: chain tab-restriction migration into startCommand"
```

---

## Rollout summary / safety

- **Default deny** is intentional: existing users `michiba` and `tanaka` will see no tabs until you assign them a group. User `a` is seeded to full access by the migration.
- **Escape hatch:** group assignment lives in `test.db`; you can always fix lockout by editing the DB directly (SQLite CLI / DB browser), exactly like managing `allowed_users`. Login itself is not a tab.
- **Two-layer enforcement:** hiding buttons (UX) + route guard (real protection against typed URLs).

## Self-Review (done while writing)

- **Spec coverage:** per-user `tab_group` column (Task 1) ✓; `tab_group` table defining tabs per group (Task 1, seeded Task 3) ✓; default = none/hidden (resolver returns empty set, Task 2; base.html `{% if %}` Task 5; route guard Task 4) ✓; user `a` = all tabs (Task 3 seed) ✓; no code touched until plan approved ✓.
- **Type/name consistency:** `parse_tab_keys`, `allowed_tabs_for`, `tab_guard`, `TabGroup`, `users.tab_group`, `group_key`, `tab_keys`, ALL_TABS used identically across Tasks 1–5.
- **Placeholder scan:** no TBD/"handle edge cases"; every code step shows concrete code. Two explicit "verify before finalizing" notes (Jinja block name in `no_access.html`; sub-route scope) are intentional checks, not placeholders.
- **Open item to confirm during execution:** the `{% block content %}` name in `base.html` (Task 5 Step 3) — verify against an existing child template before writing `no_access.html`.

# Admin Tab (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a browser-based Admin tab that lets an admin manage the `users`, `allowed_users`, and `tab_group` tables without using the Render Shell.

**Architecture:** Admin access is gated by a new canonical tab key `admin` (reuses the existing tab-restriction mechanism — no schema change). All admin routes live in a dedicated `api/admin.py` `APIRouter`, mounted into `main.py` exactly like the existing `_translator_router`. A single landing page `/admin/` renders three panels (Allowed Users, Users, Tab Groups). Lock-out protection prevents the admin from removing their own access.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite `test.db`), Jinja2 templates, Starlette `SessionMiddleware`.

**Spec:** `docs/superpowers/specs/2026-06-05-admin-tab-design.md`

**Testing note (codebase reality):** This repo has **no pytest** (see `HANDOFF_CODY_TO_CLAUDY.md`). The established verification pattern is `python -m compileall` + a standalone `assert` script for pure logic + manual browser testing. This plan follows that pattern deliberately and does NOT introduce pytest. Each task ends with `compileall` and (where logic changed) the assert script, then a commit.

**Branch:** `admin-tab-phase1` (already created).

---

## File Structure

- `api/permissions.py` — **modify**: add `require_admin(request)` helper.
- `scripts/migrate_tab_restriction.py` — **modify**: add `admin` to `ALL_TABS` so the deploy migration's group-`a` refresh never strips admin.
- `scripts/migrate_admin_tab.py` — **new**: idempotent; ensures group `a` has `admin` in `tab_keys`.
- `api/admin.py` — **new**: `TAB_DEFS`, `build_tab_keys`, local `get_db`, the `APIRouter` with `/admin/` + all panel routes, `_render_admin` helper.
- `api/main.py` — **modify**: include the admin router (one block, next to the translator include).
- `templates/admin_00.html` — **new**: three-panel admin page (extends `base.html`).
- `templates/base.html` — **modify**: add the Admin tab button, guarded by `{% if "admin" in allowed_tabs %}`.
- `scripts/check_admin_tab.py` — **new**: standalone assert for `build_tab_keys`.
- `render.yaml` — **modify**: chain `migrate_admin_tab` into `startCommand` (parity; run manually on Render).

**Why two migration touches:** `migrate_tab_restriction.py` already runs on every deploy and *rewrites* group `a`'s `tab_keys` to its `ALL_TABS` constant. If we add `admin` only via a separate script, the next run of `migrate_tab_restriction` would silently remove `admin`. So we (1) add `admin` to that constant AND (2) ship a dedicated `migrate_admin_tab.py` for explicitness and for environments where the restriction migration isn't re-run.

---

## Task 1: Add `require_admin` helper + keep group-`a` refresh admin-safe

**Files:**
- Modify: `api/permissions.py`
- Modify: `scripts/migrate_tab_restriction.py:24`

- [ ] **Step 1: Add `require_admin` to `api/permissions.py`**

Append this function to the end of `api/permissions.py` (the file already imports `Request` and `RedirectResponse`):

```python
def require_admin(request: Request):
    """Return a redirect to /no_access/ unless the session user has the 'admin' tab.

    Used as the first line of every admin route (defense in depth: hiding the
    Admin button in base.html is not sufficient on its own).
    """
    if "admin" in allowed_tabs_for(request):
        return None
    return RedirectResponse(url="/no_access/", status_code=303)
```

- [ ] **Step 2: Add `admin` to the deploy migration's tab list**

In `scripts/migrate_tab_restriction.py`, change line 24 from:

```python
ALL_TABS = "schedule,link_00,project,action,todo,diary,3d,music,game,sqlite"
```

to:

```python
ALL_TABS = "schedule,link_00,project,action,todo,diary,3d,music,game,sqlite,admin"
```

- [ ] **Step 3: Verify it compiles**

Run: `python -m compileall api/permissions.py scripts/migrate_tab_restriction.py`
Expected: `Compiling ...` lines, no `SyntaxError`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add api/permissions.py scripts/migrate_tab_restriction.py
git commit -m "permissions: add require_admin; include 'admin' in full-access tab list"
```

---

## Task 2: Idempotent migration to grant `admin` to group `a`

**Files:**
- Create: `scripts/migrate_admin_tab.py`

- [ ] **Step 1: Create `scripts/migrate_admin_tab.py`**

```python
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python -m compileall scripts/migrate_admin_tab.py`
Expected: no `SyntaxError`, exit 0.

- [ ] **Step 3: Run it against the local DB**

Run: `python -m scripts.migrate_admin_tab`
Expected: prints `Migrating database at: .../test.db` then either `+ added 'admin' to group 'a' ...` or `= group 'a' already has 'admin'`, then `Admin-tab migration complete.`

- [ ] **Step 4: Confirm the data**

Run: `python -c "import sqlite3; from api.database import get_database_path as p; c=sqlite3.connect(p()); print(c.execute(\"SELECT group_key, tab_keys FROM tab_group WHERE group_key='a'\").fetchone())"`
Expected: a tuple like `('a', 'schedule,link_00,project,action,todo,diary,3d,music,game,sqlite,admin')` — `admin` present.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_admin_tab.py
git commit -m "scripts: add idempotent migration granting 'admin' tab to group a"
```

---

## Task 3: `build_tab_keys` helper + its standalone test

This builds the pure logic first (TDD-style: write the check, watch it fail on missing import, implement, watch it pass). `api/admin.py` is created here containing only the constants and helper; the router is fleshed out in Task 4.

**Files:**
- Create: `api/admin.py` (partial — constants + helper)
- Create: `scripts/check_admin_tab.py`

- [ ] **Step 1: Write the failing check `scripts/check_admin_tab.py`**

```python
"""Standalone check for the admin tab_keys CSV builder.

No pytest needed. Run:  python -m scripts.check_admin_tab
Exits 0 on success, prints FAIL and exits 1 on any failed assertion.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.admin import build_tab_keys  # noqa: E402


def main() -> None:
    # Selected keys are returned in canonical TAB_DEFS order, CSV-joined.
    assert build_tab_keys(["project", "schedule"]) == "schedule,project"
    # Unknown keys are dropped.
    assert build_tab_keys(["schedule", "bogus"]) == "schedule"
    # The admin key is supported.
    assert build_tab_keys(["admin"]) == "admin"
    # Duplicates collapse.
    assert build_tab_keys(["todo", "todo"]) == "todo"
    # Empty selection => empty CSV (default deny).
    assert build_tab_keys([]) == ""
    assert build_tab_keys(None) == ""
    print("check_admin_tab: all assertions passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it to verify it FAILS (module not yet present)**

Run: `python -m scripts.check_admin_tab`
Expected: `ModuleNotFoundError: No module named 'api.admin'` (or `ImportError` for `build_tab_keys`).

- [ ] **Step 3: Create `api/admin.py` with constants + helper**

```python
"""Admin tab (Phase 1) — browser-based management of users, allowed_users,
and tab_group tables.

Gated by the canonical 'admin' tab key: only sessions whose resolved tab set
includes 'admin' may reach any route here (see require_admin). Mounted into the
main FastAPI app via app.include_router(...) in api/main.py, mirroring the
Translator-on-Drawings router.

Phase 1 scope (see docs/superpowers/specs/2026-06-05-admin-tab-design.md):
  - allowed_users: add / edit / delete / list
  - users:         list; set/clear tab_group only
  - tab_group:     add / edit (group_name + tab checkboxes) / delete / list
Out of scope: hard-suspend, monitoring, admin password gate, password hashing.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from api.database import ENVIRONMENT, SessionLocal
from api.models import User, AllowedUser, TabGroup
from api.permissions import allowed_tabs_for, parse_tab_keys, require_admin

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Jinja2 env for admin templates. Must register allowed_tabs_for because
# base.html (which admin_00.html extends) calls it to render the top bar.
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.globals["allowed_tabs_for"] = allowed_tabs_for
templates.env.globals["ENVIRONMENT"] = ENVIRONMENT

# Canonical tab definitions (key, label) — single source of truth for the
# tab_group checkbox editor. Order matches the top bar in base.html; 'admin'
# is last. Keys MUST match the tab_page_active values used in base.html.
TAB_DEFS = [
    ("schedule", "Schedule"),
    ("link_00", "Link"),
    ("project", "Project"),
    ("action", "Function"),
    ("todo", "To Do"),
    ("diary", "Diary/Memo"),
    ("3d", "3D Viewer"),
    ("music", "Music"),
    ("game", "Game"),
    ("sqlite", "Data"),
    ("admin", "Admin"),
]
ALL_TAB_KEYS = {key for key, _label in TAB_DEFS}


def build_tab_keys(selected) -> str:
    """Build a clean tab_keys CSV from submitted checkbox values.

    - Keeps only known keys (anything not in ALL_TAB_KEYS is dropped).
    - De-duplicates and emits keys in canonical TAB_DEFS order.
    - Returns '' for no selection (default-deny: the group sees no tabs).
    """
    chosen = set(selected or [])
    return ",".join(
        key for key, _label in TAB_DEFS if key in chosen and key in ALL_TAB_KEYS
    )
```

- [ ] **Step 4: Run the check to verify it PASSES**

Run: `python -m scripts.check_admin_tab`
Expected: `check_admin_tab: all assertions passed.`

- [ ] **Step 5: Compile and commit**

Run: `python -m compileall api/admin.py scripts/check_admin_tab.py`
Expected: no `SyntaxError`.

```bash
git add api/admin.py scripts/check_admin_tab.py
git commit -m "admin: add TAB_DEFS + build_tab_keys helper with standalone check"
```

---

## Task 4: Admin router skeleton + landing page route + mount in main.py

**Files:**
- Modify: `api/admin.py` (append router + `get_db` + `_render_admin` + `/admin/` GET)
- Modify: `api/main.py:1928-1929` (add include after the translator include)

- [ ] **Step 1: Append the DB dependency, render helper, router, and landing route to `api/admin.py`**

Add to the END of `api/admin.py`:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter()


def _render_admin(request: Request, db: Session,
                  message: str = "", message_color: str = "#0f0"):
    """Render the admin landing page with all three panels."""
    allowed_users = db.query(AllowedUser).order_by(AllowedUser.id).all()
    users = db.query(User).order_by(User.username).all()
    groups = db.query(TabGroup).order_by(TabGroup.group_key).all()
    # Per group, the set of allowed keys — used to pre-check the checkboxes.
    group_keysets = {g.id: parse_tab_keys(g.tab_keys) for g in groups}
    return templates.TemplateResponse("admin_00.html", {
        "request": request,
        "login_username": request.session.get("login_username"),
        "time_zone": request.session.get("time_zone"),
        "tab_page_active": "admin",
        "today": "",
        "allowed_users": allowed_users,
        "users": users,
        "groups": groups,
        "group_keysets": group_keysets,
        "tab_defs": TAB_DEFS,
        "message": message,
        "message_color": message_color,
    })


@router.get("/admin/")
async def admin_home(request: Request, db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    return _render_admin(request, db)
```

- [ ] **Step 2: Mount the router in `api/main.py`**

In `api/main.py`, immediately after these existing lines (around 1928-1929):

```python
from translator_on_drawings.routes import router as _translator_router  # noqa: E402
app.include_router(_translator_router)
```

add:

```python
from api.admin import router as _admin_router  # noqa: E402
app.include_router(_admin_router)
```

- [ ] **Step 3: Verify it compiles**

Run: `python -m compileall api/admin.py api/main.py`
Expected: no `SyntaxError`.

- [ ] **Step 4: Verify the app imports without error**

Run: `python -c "import api.main"`
Expected: prints the existing env/database banner lines, no traceback.

- [ ] **Step 5: Commit**

```bash
git add api/admin.py api/main.py
git commit -m "admin: add /admin/ landing route and mount router in main"
```

---

## Task 5: The admin page template (three panels)

**Files:**
- Create: `templates/admin_00.html`

Note: each editable row is ONE `<form>`; secondary actions (Delete) use a second submit button with `formaction` so we never split a form across table cells. The delete handler reads only `row_id`, so the extra fields submitted to it are harmless.

- [ ] **Step 1: Create `templates/admin_00.html`**

```html
{% extends "base.html" %}
{% block content %}
<style>
    .admin_wrap { padding: 16px; font-family: Arial, sans-serif; color: #ccc; background-color: #222; }
    .admin_wrap h1 { color: #0f0; font-size: 18px; margin: 0 0 8px; }
    .admin_wrap h2 { color: #0f0; font-size: 15px; margin: 18px 0 6px; border-bottom: 1px solid #333; padding-bottom: 3px; }
    .admin_wrap h3 { color: #0f0; font-size: 13px; margin: 10px 0 4px; }
    .admin_msg { margin: 8px 0; font-size: 13px; }
    .admin_wrap form { margin: 0 0 6px; }
    .admin_wrap input[type="text"],
    .admin_wrap input[type="email"] {
        background-color: #333; color: #eee; border: 1px solid #555;
        padding: 3px 5px; font-size: 12px; margin: 0 2px;
    }
    .admin_wrap button {
        background-color: #444; color: #aaa; border: 1px solid #555;
        padding: 3px 8px; font-size: 12px; cursor: pointer; margin-left: 4px;
    }
    .admin_wrap button:hover { color: #0f0; }
    .row_id { color: #666; font-size: 11px; }
    .tabbox { display: inline-block; margin-right: 10px; font-size: 11px; white-space: nowrap; }
    .group_block { border-bottom: 1px solid #333; padding-bottom: 8px; margin-bottom: 8px; }
</style>

<div class="admin_wrap">
    <h1>Admin</h1>
    {% if message %}<div class="admin_msg" style="color: {{ message_color }};">{{ message }}</div>{% endif %}

    <!-- ===================== Panel 1: Allowed Users ===================== -->
    <h2>Allowed Users (sign-up allowlist)</h2>
    {% for au in allowed_users %}
    <form action="/admin/allowed_users/edit/" method="post">
        <span class="row_id">#{{ au.id }}</span>
        <input type="hidden" name="row_id" value="{{ au.id }}">
        <input type="text"  name="username" value="{{ au.username or '' }}" placeholder="username" required>
        <input type="email" name="email"    value="{{ au.email or '' }}"    placeholder="email" required>
        <input type="text"  name="password" value="{{ au.password or '' }}" placeholder="password" required>
        <button type="submit">Save</button>
        <button type="submit" formaction="/admin/allowed_users/delete/"
                onclick="return confirm('Delete allowed user {{ au.username }}?');">Delete</button>
    </form>
    {% endfor %}
    <h3>Add allowed user</h3>
    <form action="/admin/allowed_users/add/" method="post">
        <input type="text"  name="username" placeholder="username" required>
        <input type="email" name="email"    placeholder="email" required>
        <input type="text"  name="password" placeholder="password" required>
        <button type="submit">Add</button>
    </form>

    <!-- ===================== Panel 2: Users ===================== -->
    <h2>Users (assign / clear tab group)</h2>
    {% for u in users %}
    <form action="/admin/users/set_group/" method="post">
        <span class="row_id">#{{ u.id }}</span>
        <input type="hidden" name="user_id" value="{{ u.id }}">
        <strong>{{ u.username }}</strong>
        <span style="color:#888;">&lt;{{ u.email or '' }}&gt;</span>
        &nbsp;group:
        <input type="text" name="tab_group" value="{{ u.tab_group or '' }}" placeholder="(none = no access)">
        <button type="submit">Set group</button>
    </form>
    {% endfor %}

    <!-- ===================== Panel 3: Tab Groups ===================== -->
    <h2>Tab Groups</h2>
    {% for g in groups %}
    <form action="/admin/tab_group/edit/" method="post" class="group_block">
        <span class="row_id">#{{ g.id }}</span>
        key: <strong style="color:#0f0;">{{ g.group_key }}</strong>
        <input type="hidden" name="row_id" value="{{ g.id }}">
        &nbsp;name: <input type="text" name="group_name" value="{{ g.group_name or '' }}">
        <div style="margin:4px 0;">
            {% for key, label in tab_defs %}
            <label class="tabbox">
                <input type="checkbox" name="tabs" value="{{ key }}"
                       {% if key in group_keysets[g.id] %}checked{% endif %}> {{ label }}
            </label>
            {% endfor %}
        </div>
        <button type="submit">Save group</button>
        <button type="submit" formaction="/admin/tab_group/delete/"
                onclick="return confirm('Delete group {{ g.group_key }}?');">Delete group</button>
    </form>
    {% endfor %}

    <h3>Add a new group</h3>
    <form action="/admin/tab_group/add/" method="post">
        key: <input type="text" name="group_key" placeholder="e.g. b" required>
        &nbsp;name: <input type="text" name="group_name" placeholder="e.g. Site staff">
        <div style="margin:4px 0;">
            {% for key, label in tab_defs %}
            <label class="tabbox">
                <input type="checkbox" name="tabs" value="{{ key }}"> {{ label }}
            </label>
            {% endfor %}
        </div>
        <button type="submit">Add group</button>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 2: Confirm the template loads (route renders)**

Start the app in the background and curl the route as an admin is not trivial without a session; instead verify the template parses by importing the app (Jinja loads lazily, so do a quick render check):

Run:
```bash
python -c "
from api.admin import templates
t = templates.get_template('admin_00.html')
print('template OK:', t.name)
"
```
Expected: `template OK: admin_00.html` (a Jinja `TemplateSyntaxError` here means the HTML has a template bug to fix).

- [ ] **Step 3: Commit**

```bash
git add templates/admin_00.html
git commit -m "admin: add admin_00.html three-panel management page"
```

---

## Task 6: Allowed Users routes (add / edit / delete)

**Files:**
- Modify: `api/admin.py` (append three routes)

- [ ] **Step 1: Append the Allowed Users routes to `api/admin.py`**

```python
# ----------------------- Allowed Users -----------------------

@router.post("/admin/allowed_users/add/")
async def allowed_users_add(request: Request,
                            username: str = Form(...),
                            email: str = Form(...),
                            password: str = Form(...),
                            db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    if db.query(AllowedUser).filter(AllowedUser.email == email).first():
        return _render_admin(request, db,
                             message=f"An allowed user with email {email} already exists.",
                             message_color="#f00")
    try:
        db.add(AllowedUser(username=username, email=email, password=password))
        db.commit()
    except Exception as e:
        db.rollback()
        return _render_admin(request, db, message=f"Add failed: {e}", message_color="#f00")
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/admin/allowed_users/edit/")
async def allowed_users_edit(request: Request,
                             row_id: int = Form(...),
                             username: str = Form(...),
                             email: str = Form(...),
                             password: str = Form(...),
                             db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    row = db.query(AllowedUser).filter(AllowedUser.id == row_id).first()
    if not row:
        return _render_admin(request, db, message="Allowed user not found.", message_color="#f00")
    clash = db.query(AllowedUser).filter(
        AllowedUser.email == email, AllowedUser.id != row_id
    ).first()
    if clash:
        return _render_admin(request, db,
                             message=f"Email {email} is already used by another row.",
                             message_color="#f00")
    try:
        row.username = username
        row.email = email
        row.password = password
        db.commit()
    except Exception as e:
        db.rollback()
        return _render_admin(request, db, message=f"Edit failed: {e}", message_color="#f00")
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/admin/allowed_users/delete/")
async def allowed_users_delete(request: Request,
                               row_id: int = Form(...),
                               db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    row = db.query(AllowedUser).filter(AllowedUser.id == row_id).first()
    if row:
        db.delete(row)
        db.commit()
    return RedirectResponse(url="/admin/", status_code=303)
```

Note: the delete form posts the row's username/email/password too, but this handler ignores them (reads only `row_id`). That is intentional — it lets the Save and Delete buttons share one form via `formaction`.

- [ ] **Step 2: Compile and import-check**

Run: `python -m compileall api/admin.py && python -c "import api.main"`
Expected: no `SyntaxError`, no traceback.

- [ ] **Step 3: Commit**

```bash
git add api/admin.py
git commit -m "admin: add allowed_users add/edit/delete routes"
```

---

## Task 7: Users route (set / clear tab_group) with self-lock-out guard

**Files:**
- Modify: `api/admin.py` (append one route)

- [ ] **Step 1: Append the Users route to `api/admin.py`**

```python
# ----------------------- Users -----------------------

@router.post("/admin/users/set_group/")
async def users_set_group(request: Request,
                          user_id: int = Form(...),
                          tab_group: str = Form(""),
                          db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return _render_admin(request, db, message="User not found.", message_color="#f00")
    new_group = tab_group.strip()
    # Lock-out protection: the current admin must not move THEMSELVES into a
    # group that lacks the 'admin' tab (or clear their group entirely).
    if user.username == request.session.get("login_username"):
        target_keys = set()
        if new_group:
            g = db.query(TabGroup).filter(TabGroup.group_key == new_group).first()
            target_keys = parse_tab_keys(g.tab_keys) if g else set()
        if "admin" not in target_keys:
            return _render_admin(request, db,
                                 message="Refused: that change would remove your own admin access.",
                                 message_color="#f00")
    user.tab_group = new_group  # '' clears => default deny (soft-suspend)
    db.commit()
    return RedirectResponse(url="/admin/", status_code=303)
```

- [ ] **Step 2: Compile and import-check**

Run: `python -m compileall api/admin.py && python -c "import api.main"`
Expected: no `SyntaxError`, no traceback.

- [ ] **Step 3: Commit**

```bash
git add api/admin.py
git commit -m "admin: add users set_group route with self-lock-out guard"
```

---

## Task 8: Tab Group routes (add / edit / delete) with lock-out + orphan protection

**Files:**
- Modify: `api/admin.py` (append three routes)

- [ ] **Step 1: Append the Tab Group routes to `api/admin.py`**

```python
# ----------------------- Tab Groups -----------------------

@router.post("/admin/tab_group/add/")
async def tab_group_add(request: Request,
                        group_key: str = Form(...),
                        group_name: str = Form(""),
                        tabs: list[str] = Form(default=[]),
                        db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    key = group_key.strip()
    if not key:
        return _render_admin(request, db, message="Group key is required.", message_color="#f00")
    if db.query(TabGroup).filter(TabGroup.group_key == key).first():
        return _render_admin(request, db, message=f"Group '{key}' already exists.", message_color="#f00")
    try:
        db.add(TabGroup(group_key=key, group_name=group_name.strip(),
                        tab_keys=build_tab_keys(tabs)))
        db.commit()
    except Exception as e:
        db.rollback()
        return _render_admin(request, db, message=f"Add failed: {e}", message_color="#f00")
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/admin/tab_group/edit/")
async def tab_group_edit(request: Request,
                         row_id: int = Form(...),
                         group_name: str = Form(""),
                         tabs: list[str] = Form(default=[]),
                         db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    group = db.query(TabGroup).filter(TabGroup.id == row_id).first()
    if not group:
        return _render_admin(request, db, message="Group not found.", message_color="#f00")
    new_keys = build_tab_keys(tabs)
    # Lock-out protection: if this is the current admin's own group, the
    # 'admin' tab must remain in it.
    me = db.query(User).filter(
        User.username == request.session.get("login_username")
    ).first()
    if me and me.tab_group == group.group_key and "admin" not in parse_tab_keys(new_keys):
        return _render_admin(request, db,
                             message="Refused: that change would remove your own admin access.",
                             message_color="#f00")
    group.group_name = group_name.strip()
    group.tab_keys = new_keys
    db.commit()
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/admin/tab_group/delete/")
async def tab_group_delete(request: Request,
                           row_id: int = Form(...),
                           db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    group = db.query(TabGroup).filter(TabGroup.id == row_id).first()
    if not group:
        return _render_admin(request, db, message="Group not found.", message_color="#f00")
    me = db.query(User).filter(
        User.username == request.session.get("login_username")
    ).first()
    if me and me.tab_group == group.group_key:
        return _render_admin(request, db,
                             message="Refused: you cannot delete the group you belong to.",
                             message_color="#f00")
    assigned = db.query(User).filter(User.tab_group == group.group_key).count()
    if assigned > 0:
        return _render_admin(request, db,
                             message=f"Refused: {assigned} user(s) still assigned to '{group.group_key}'.",
                             message_color="#f00")
    db.delete(group)
    db.commit()
    return RedirectResponse(url="/admin/", status_code=303)
```

- [ ] **Step 2: Compile and import-check**

Run: `python -m compileall api/admin.py && python -c "import api.main"`
Expected: no `SyntaxError`, no traceback.

- [ ] **Step 3: Re-run the logic check (build_tab_keys still correct)**

Run: `python -m scripts.check_admin_tab`
Expected: `check_admin_tab: all assertions passed.`

- [ ] **Step 4: Commit**

```bash
git add api/admin.py
git commit -m "admin: add tab_group add/edit/delete with lock-out + orphan guards"
```

---

## Task 9: Add the Admin tab button + chain the migration in render.yaml

**Files:**
- Modify: `templates/base.html:588` (after the `sqlite` tab `{% endif %}`)
- Modify: `render.yaml:6`

- [ ] **Step 1: Add the Admin button in `templates/base.html`**

In `templates/base.html`, find the sqlite tab block ending at line 588:

```html
            {% if "sqlite" in allowed_tabs %}
            <form action="/sqlite/" method="get">

                <button type="submit" style="background-color: #444; color: {{ "#f00" if tab_page_active == "sqlite" else "#aaa" }};">Data</button>
            </form>
            {% endif %}
```

Immediately AFTER that `{% endif %}` (i.e., before the blank lines and the `select_time_zone` form), insert:

```html
            {% if "admin" in allowed_tabs %}
            <form action="/admin/" method="get">
                <button type="submit" style="background-color: #444; color: {{ "#0f0" if tab_page_active == "admin" else "#aaa" }};">Admin</button>
            </form>
            {% endif %}
```

- [ ] **Step 2: Chain the migration into `render.yaml`**

In `render.yaml`, change line 6 from:

```yaml
    startCommand: python -m scripts.migrate_daily_tasks && python -m scripts.migrate_repeat_tasks && python -m scripts.migrate_tab_restriction && uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

to:

```yaml
    startCommand: python -m scripts.migrate_daily_tasks && python -m scripts.migrate_repeat_tasks && python -m scripts.migrate_tab_restriction && python -m scripts.migrate_admin_tab && uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 3: Confirm the base template still parses**

Run:
```bash
python -c "
from api.admin import templates
print('base OK:', templates.get_template('base.html').name)
print('admin OK:', templates.get_template('admin_00.html').name)
"
```
Expected: `base OK: base.html` and `admin OK: admin_00.html` (no `TemplateSyntaxError`).

- [ ] **Step 4: Commit**

```bash
git add templates/base.html render.yaml
git commit -m "admin: show Admin tab button; chain migrate_admin_tab in render startCommand"
```

---

## Task 10: Full local verification (manual browser checklist)

No code changes — this task runs the app and confirms behavior end to end. Precondition: Task 2's migration has been run locally, so group `a` includes `admin`, and user `a` is in group `a`.

**Files:** none (verification only).

- [ ] **Step 1: Final static checks**

Run:
```bash
python -m compileall api scripts
python -m scripts.check_tab_permissions
python -m scripts.check_admin_tab
```
Expected: no `SyntaxError`; both checks print `all assertions passed.`

- [ ] **Step 2: Start the app**

Run (background): `uvicorn api.main:app --host 127.0.0.1 --port 8000`
Expected: `Application startup complete.`

- [ ] **Step 3: Admin sees the tab**

In a browser, log in as user **`a`**. On the top bar, confirm the **Admin** button is present. Click it → the Admin page loads at `/admin/` with three panels (Allowed Users, Users, Tab Groups).

- [ ] **Step 4: Non-admin is blocked**

Using the Users panel, create/confirm a test user in a group WITHOUT `admin` (e.g. make a group `b` with only `schedule`, assign a test user to it). Log in as that user: the **Admin** button must NOT appear, and visiting `/admin/` directly must redirect to `/no_access/`.

- [ ] **Step 5: Allowed Users CRUD**

As admin: **Add** an allowed user (username/email/password). Then open the sign-up page and register with exactly those credentials → sign-up succeeds. Back in Admin, **edit** that allowed-user row (change username) → Save persists. **Delete** the row → it disappears.

- [ ] **Step 6: Users soft-suspend**

As admin, set a non-admin test user's group field to empty and **Set group**. Log in as that user → they can log in but every tab redirects to `/no_access/` (soft-suspend confirmed). Restore their group afterward.

- [ ] **Step 7: Tab Groups CRUD + checkbox editor**

As admin: **Add** a group with a few tabs ticked → it appears with those tabs checked. **Edit** it (tick/untick tabs) → Save persists the new set. **Delete** an unused group → removed.

- [ ] **Step 8: Lock-out protection**

As admin (user `a`, group `a`): on group `a`, untick **Admin** and Save → must be **refused** with the warning message, and `admin` stays checked after reload. Try to **Delete** group `a` → refused (you belong to it). Try to delete any group that still has users assigned → refused with the orphan warning.

- [ ] **Step 9: Stop the app**

Stop the background uvicorn process.

- [ ] **Step 10: Deploy note (no code)**

After pushing the branch and merging, run the migration manually in the Render Shell per the standing project rule:
```
python -m scripts.migrate_admin_tab
```
Verify on remote that user `a` still sees the Admin tab.

---

## Definition of Done

- Admin (group `a`) can, from the browser (local and remote): approve/edit/delete allowed users, assign/clear user tab groups, and create/edit/delete tab groups via checkboxes.
- Non-admins cannot see or reach the Admin tab.
- Admin cannot lock themselves out (group edit/delete and user set_group guards all hold).
- `compileall` clean; `check_tab_permissions` and `check_admin_tab` pass; manual checklist passes.
- `migrate_admin_tab` run on Render.

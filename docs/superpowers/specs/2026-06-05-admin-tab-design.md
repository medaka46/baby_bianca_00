# Admin Tab (Phase 1) — Design Spec

**Date:** 2026-06-05
**Status:** Approved for implementation planning
**Scope:** Phase 1 only — a browser-based Admin tab to manage the `users`, `allowed_users`, and `tab_group` tables, gated by an `admin` tab permission.

---

## Background & Motivation

The app already has a per-user **tab-restriction** access-control feature (see commits `0f1e150`…`6d4d592` and `docs/superpowers/plans/2026-06-01-user-tab-restriction.md`):

- `users.tab_group` points each user at a row in the `tab_group` table.
- `tab_group.tab_keys` is a CSV of allowed top-bar tab keys.
- `api/permissions.py` resolves `login_username → users.tab_group → tab_group.tab_keys → allowed set`, with **default deny**.
- `allowed_users` is a pre-approval allowlist consulted **only at sign-up** (`POST /login_signup/add_user/`); login (`check_user`) reads only the `users` table.

**Problem:** On the remote (Render) environment, the only way to manage these tables is the Render Shell (raw SQL / migration scripts). This is slow and error-prone. In particular, with an empty `allowed_users` table on remote, **nobody new can sign up** until a row is inserted by hand.

**Goal of Phase 1:** Provide an in-browser Admin tab so the admin can manage all three tables directly — approve sign-ups, assign/clear tab groups (soft-suspend), and define groups — without using the Render Shell.

### Out of scope (deferred to Phase 2+)
- **Hard-suspend** (`is_active` flag on `users` + login/request rejection).
- **Real-time monitoring** (`last_seen` column + middleware + "who's online" view).
- **Admin password gate** (an extra password prompt to enter the Admin tab).
- **Security hardening:** move `secret_key` (currently hardcoded `"your_secret_key"` at `api/main.py:45`) to an env var; password **hashing** + user self-service **password change** (passwords remain plaintext for now).

These are recorded here only so they are not forgotten; they are NOT built in Phase 1.

---

## Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Admin scope for this cycle | **Phase 1 only** (admin tab + edit 3 tables) |
| 2 | How admin status is identified | **Reuse the tab system** — a new `admin` tab key (no new column, no hardcoded usernames) |
| 3 | Operations per table | **Minimal-but-complete recommended set** (see below) |
| 4 | `tab_keys` editor | **Checkbox list** of all tabs (app builds the CSV) |
| 5 | `allowed_users` password display | **Show plaintext** (simple way) — hashing deferred to Phase 2 |
| 6 | Code organization | **Dedicated `api/admin.py` `APIRouter`**, included into `main.py` (mirrors existing `_translator_router`) |

### Operations per table
- **`allowed_users`** — Add, Edit, Delete, List.
- **`users`** — List; Edit **only `tab_group`** (assign/clear) per user. No create, no delete.
- **`tab_group`** — Add, Edit (`group_name` + tab checkboxes), Delete, List.

---

## Architecture

### Access control
- Add **`admin`** to the canonical tab-key set. New full tab list:
  `schedule, link_00, project, action, todo, diary, 3d, music, game, sqlite, admin`
- `templates/base.html`: wrap the new **Admin** tab button in `{% if 'admin' in <allowed set> %}`, reusing the exact pattern already applied to every other tab.
- New helper in `api/permissions.py`:

  ```python
  def require_admin(request: Request):
      """Return a redirect to /no_access/ unless the session user has the 'admin' tab."""
      if "admin" in allowed_tabs_for(request):
          return None
      return RedirectResponse(url="/no_access/", status_code=303)
  ```
- **Every** admin route calls `require_admin(request)` first and returns the redirect if non-None (defense in depth — hiding the button is not sufficient).

Admin access is therefore fully data-driven via `tab_group.tab_keys`. No schema change.

### Data model & migration
- **No new tables or columns.** `admin` is just another value inside `tab_group.tab_keys`.
- New idempotent migration `scripts/migrate_admin_tab.py`:
  1. Ensure group **`a`** has **`admin`** appended to its `tab_keys` (so the admin is not locked out on first deploy).
  2. Safe to run repeatedly (check membership before appending).
- Extend the `ALL_TABS` constant used by seed/migration logic to include `admin`.
- Chain `python -m scripts.migrate_admin_tab` into `render.yaml` `startCommand` for parity, **but run it manually in the Render Shell after deploy** (standing project rule: Render does not auto-apply migrations).

### Code organization
- New module **`api/admin.py`** exposing an `APIRouter` with all admin routes.
- `main.py` includes it with a single `app.include_router(...)` line, exactly like the existing `_translator_router` (`api/main.py:1929`).
- This keeps the security-sensitive admin surface isolated, small, and easy to reason about, and avoids growing the already 2,678-line `main.py`.

---

## Components & Routes

Single landing page **`GET /admin/`** → `templates/admin_00.html`, three panels. All POST handlers commit then redirect `303` back to `/admin/`. All handlers call `require_admin` first.

### Panel 1 — Allowed Users (`allowed_users`)
- List: username, email, password (plaintext).
- `POST /admin/allowed_users/add/` — username + email + password.
- `POST /admin/allowed_users/edit/` — edit a row.
- `POST /admin/allowed_users/delete/` — delete a row.

### Panel 2 — Users (`users`)
- List: username, email, current `tab_group`.
- `POST /admin/users/set_group/` — set or clear a user's `tab_group` (the soft-suspend lever).
- No create, no delete.

### Panel 3 — Tab Groups (`tab_group`)
- List: `group_key`, `group_name`, allowed tabs (rendered from `tab_keys`).
- `POST /admin/tab_group/add/` — new group.
- `POST /admin/tab_group/edit/` — `group_name` + checkbox list of all tabs (incl. Admin); server builds the `tab_keys` CSV from the ticked boxes.
- `POST /admin/tab_group/delete/` — delete a group.

### Checkbox → CSV logic
A small pure helper builds the CSV from the submitted checkbox values, validating each against the known tab-key set. This is the one piece of pure logic that gets a standalone assert check.

---

## Lock-out Protection (safety)

To guarantee the admin cannot accidentally remove their own access:

- **Editing a `tab_group`:** if the edit would remove `admin` from the group the **current admin user belongs to**, the server **refuses** and shows a warning instead of committing.
- **Deleting a `tab_group`:** refuse/warn if it is the current admin's own group, **or** if any users are still assigned to it (avoid orphaning users into default-deny unexpectedly).

These checks live in the admin route handlers, before commit.

---

## Error Handling
- Non-admin access to any `/admin/...` route → redirect to `/no_access/` (303).
- Invalid form input (e.g., duplicate `group_key`, missing fields) → re-render `/admin/` with a red message, no partial commit (`db.rollback()` on exception), following the existing pattern in `add_user`.
- Lock-out-protected actions → warning message, no commit.

---

## Testing & Verification

Matches this repo's established practice (no pytest; see `HANDOFF_CODY_TO_CLAUDY.md`):

1. `python -m compileall api scripts` — confirm everything imports.
2. Standalone assert script (e.g., `scripts/check_admin_tab.py`) for the checkbox→CSV builder logic, mirroring `scripts/check_tab_permissions.py`.
3. Manual browser checklist:
   - Admin user (group `a`) sees the **Admin** tab; non-admin does not, and a direct `/admin/` visit redirects to `/no_access/`.
   - Allowed Users: add → new sign-up succeeds with that password; edit; delete.
   - Users: set/clear `tab_group`; cleared user can log in but hits `/no_access/` on every tab (soft-suspend confirmed).
   - Tab Groups: add; edit via checkboxes; delete.
   - Lock-out protection blocks removing `admin` from / deleting the admin's own group.

---

## Files Touched (anticipated)

- `api/models.py` — none required (no schema change); confirm `AllowedUser`, `TabGroup`, `User` import cleanly into the admin module.
- `api/permissions.py` — add `require_admin(request)`; extend `ALL_TABS`-style constant if defined here.
- `api/admin.py` — **new**: `APIRouter` with `/admin/` + all panel routes + checkbox→CSV helper.
- `api/main.py` — one `app.include_router(...)` line; ensure `allowed_tabs_for` Jinja global already covers the new tab (it does).
- `templates/admin_00.html` — **new**: three-panel admin page.
- `templates/base.html` — add the **Admin** tab button, guarded by `{% if 'admin' in ... %}`.
- `scripts/migrate_admin_tab.py` — **new**: idempotent; append `admin` to group `a`'s `tab_keys`.
- `scripts/check_admin_tab.py` — **new**: standalone assert for the CSV builder.
- `render.yaml` — chain the new migration into `startCommand` (parity; manual run on Render).

---

## Definition of Done (Phase 1)
- Admin (group `a`) can, from the browser on both local and remote: approve/edit/delete allowed users, assign/clear user tab groups, and create/edit/delete tab groups via checkboxes.
- Non-admins cannot see or reach the Admin tab.
- Admin cannot lock themselves out.
- `compileall` clean; CSV-builder assert passes; manual checklist passes.
- Migration run on Render.

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

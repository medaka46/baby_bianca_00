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

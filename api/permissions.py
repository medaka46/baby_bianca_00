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


def require_admin(request: Request):
    """Return a redirect to /no_access/ unless the session user has the 'admin' tab.

    Used as the first line of every admin route (defense in depth: hiding the
    Admin button in base.html is not sufficient on its own).
    """
    if "admin" in allowed_tabs_for(request):
        return None
    return RedirectResponse(url="/no_access/", status_code=303)


# Ordered (tab_key, landing URL). The order defines the priority used to pick a
# user's first allowed tab after login. Keys match tab_page_active in base.html.
TAB_LANDING = [
    ("schedule", "/schedule/"),
    ("link_00", "/link_00/"),
    ("project", "/project/"),
    ("action", "/action/"),
    ("todo", "/todo/"),
    ("diary", "/diary/"),
    ("3d", "/3d/"),
    ("music", "/music/"),
    ("game", "/game/"),
    ("sqlite", "/sqlite/"),
    ("admin", "/admin/"),
]


def landing_url_for(request: Request) -> str:
    """Return the landing URL of the first tab the user may access.

    Used right after login/sign-up/time-zone selection so a user is sent to a
    tab they are actually allowed to see, instead of always the Schedule page.
    Falls back to /no_access/ when the user has no allowed tabs (default deny).
    """
    allowed = allowed_tabs_for(request)
    for key, url in TAB_LANDING:
        if key in allowed:
            return url
    return "/no_access/"

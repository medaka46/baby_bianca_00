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

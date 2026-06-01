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

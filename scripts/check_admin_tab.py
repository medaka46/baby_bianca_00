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

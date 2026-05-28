# Repeat Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Repeat Task" feature to the Schedule tab so a user can create a single template (e.g. "Standup, every weekday, until end of month") that displays as virtual occurrences in the Today area and the weekly grid — without writing one row per occurrence.

**Architecture:** Store each repeat task as ONE row in the `schedules` table (`is_repeat_task=1`) with a `repeat_type`, optional `repeat_weekdays` (CSV of Python weekday ints), and a `range_start`/`range_end` window. The two read paths that build `df_combined` (the main `/schedule/` GET and the edit-view GET) expand each template into virtual per-date dicts that mirror the daily-task render shape, so the existing Jinja template needs no changes to *display* them. A new POST route `/schedule/add_repeat_task/` writes the template row.

**Tech Stack:** FastAPI · SQLAlchemy · SQLite · Jinja2 · pandas (already in the read pipeline). No test framework in this repo — verification uses small Python smoke checks and manual browser checks against the running dev server.

**Conventions in this codebase (read before starting):**
- Daily tasks use `is_daily_task=1` + `task_date` (TZ-independent). Mirror that shape.
- `start_datetime`/`end_datetime` are NOT NULL → repeat-template rows fill them with a sentinel (UTC midnight of `range_start`).
- The Jinja template branches on `item.is_daily_task` to show the `🟩 ` prefix. Virtual repeat-task dicts will set `is_daily_task=1` (same visual) plus `is_repeat_task=1` so future code can distinguish if needed.
- Migrations: one-off scripts in `scripts/`, run via `python -m scripts.<name>`, idempotent (guarded `ALTER TABLE`s). See `scripts/migrate_daily_tasks.py` as the canonical example.
- Python venv: `.py31205` lives in the parent directory; activate before running anything.

---

## Progress so far (already completed in prior session — do NOT redo)

- [x] **A. Button added in template** — `templates/schedule_indicate_00.html:120` now has `<button … formaction="/schedule/add_repeat_task/">Add Repeat Task</button>` just right of `Add Daily Task`.
- [x] **B. Model columns added** — `api/models.py` Schedule class has `is_repeat_task`, `repeat_type`, `repeat_weekdays`, `range_start`, `range_end` (see lines around the `is_daily_task` block).

The remaining tasks are 1 → 4 below.

---

## File Structure

| File | Role | Status |
|---|---|---|
| `api/models.py` | Schedule model with the 5 new repeat columns | Done (prior session) |
| `templates/schedule_indicate_00.html` | Add-Repeat-Task button + new form selectors | Button done; form selectors pending (Task 2) |
| `scripts/migrate_repeat_tasks.py` | One-off idempotent migration adding the 5 columns | Pending (Task 1) |
| `api/main.py` | New POST route + extension of the two `df_combined` builders | Pending (Tasks 2–4) |
| `api/repeat_tasks.py` | Pure helper: `expand_repeat_template(row, dates, time_zone) → list[dict]` | Pending (Task 3 creates it) |

Splitting the expansion logic into its own helper keeps `api/main.py` (already large) free of new branching, and makes the helper trivially smoke-testable in a Python REPL.

---

## Task 1: Database migration

**Files:**
- Create: `scripts/migrate_repeat_tasks.py`

- [ ] **Step 1.1: Create the migration script**

Create `scripts/migrate_repeat_tasks.py` with this exact content:

```python
"""One-off migration: add repeat-task columns to the schedules table.

Adds five columns used by the Repeat Task feature:
  is_repeat_task   INTEGER DEFAULT 0
  repeat_type      TEXT       -- 'every_day' | 'every_weekday' | 'every_specific_weekday'
  repeat_weekdays  TEXT       -- CSV of Python weekday ints, e.g. '0,2,4' (Mon=0..Sun=6)
  range_start      DATE
  range_end        DATE

Run once, locally and on Render.

  Local:   python -m scripts.migrate_repeat_tasks
  Render:  Shell tab -> python -m scripts.migrate_repeat_tasks

Idempotent: re-running is safe (each column add is guarded).
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import get_database_path  # noqa: E402


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def add_columns(conn: sqlite3.Connection) -> None:
    specs = [
        ("is_repeat_task", "INTEGER DEFAULT 0"),
        ("repeat_type", "TEXT"),
        ("repeat_weekdays", "TEXT"),
        ("range_start", "DATE"),
        ("range_end", "DATE"),
    ]
    for name, sql_type in specs:
        if not column_exists(conn, "schedules", name):
            conn.execute(f"ALTER TABLE schedules ADD COLUMN {name} {sql_type}")
            print(f"  + added column schedules.{name}")
        else:
            print(f"  = column schedules.{name} already exists")


def main() -> None:
    db_path = get_database_path()
    print(f"Migrating database at: {db_path}")
    if not os.path.exists(db_path):
        print("Database file does not exist - nothing to migrate.")
        return
    conn = sqlite3.connect(db_path)
    try:
        add_columns(conn)
        conn.commit()
        print("Repeat-task columns migration complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 1.2: Run the migration locally**

Run from the project root with the project's interpreter:

```bash
python -m scripts.migrate_repeat_tasks
```

Expected output (first run):
```
Migrating database at: …/test.db
  + added column schedules.is_repeat_task
  + added column schedules.repeat_type
  + added column schedules.repeat_weekdays
  + added column schedules.range_start
  + added column schedules.range_end
Repeat-task columns migration complete.
```

- [ ] **Step 1.3: Re-run to confirm idempotence**

Run the same command again:

```bash
python -m scripts.migrate_repeat_tasks
```

Expected: every line is `= column schedules.<name> already exists` and the final `Repeat-task columns migration complete.` Confirms safe to re-run on Render.

- [ ] **Step 1.4: Verify the columns are visible to SQLite**

```bash
python -c "import sqlite3; c=sqlite3.connect('test.db'); print([r[1] for r in c.execute('PRAGMA table_info(schedules)')])"
```

Expected: the printed list includes all five new column names alongside `is_daily_task`, `task_date`, etc.

- [ ] **Step 1.5: Commit**

```bash
git add scripts/migrate_repeat_tasks.py api/models.py
git commit -m "add Repeat Task schema columns + migration script"
```

(Note: `api/models.py` was edited in the prior session but never committed — include it in this commit.)

---

## Task 2: Form UI — add repeat-type, weekday, and range selectors

**Files:**
- Modify: `templates/schedule_indicate_00.html` — header form area (~lines 91–122)

The current form has one row of inputs feeding `/schedule/add_task/`. The two existing buttons (`Add Task`, `Add Daily Task`) hijack the form via `formaction`. We add three more selector groups that the `Add Repeat Task` button will use; the other buttons simply ignore them (FastAPI Form fields are tolerant of extra/missing values when typed `Form(None)`).

- [ ] **Step 2.1: Add the three selectors inside the form, just before the buttons**

Find this block in `templates/schedule_indicate_00.html` (around line 117):

```html
            <input type="text" name="status" placeholder="Enter status..." style="background-color: #444; color: #fff;" oninput="this.style.backgroundColor = this.value ? '#444' : '#fff'; this.style.color = '#999'">
            <button type="submit" style="background-color: #444; color: #0f0;">Add Task</button>
```

Insert the following block BETWEEN the `status` input and the `Add Task` button:

```html
            {# Repeat-task selectors — only consumed by the Add Repeat Task button. #}
            <select name="repeat_type" id="repeat_type_select"
                    style="background-color: #444; color: #aaa;"
                    onchange="document.getElementById('repeat_weekdays_group').style.display = (this.value === 'every_specific_weekday') ? 'inline-block' : 'none';">
                <option value="every_day">Every day</option>
                <option value="every_weekday">Every weekday (Mon–Fri)</option>
                <option value="every_specific_weekday">Every specific weekday</option>
            </select>
            <span id="repeat_weekdays_group" style="display: none; color: #aaa; padding: 0 5px;">
                {% for label, val in [('Mon','0'),('Tue','1'),('Wed','2'),('Thu','3'),('Fri','4'),('Sat','5'),('Sun','6')] %}
                    <label style="margin-right: 4px;">
                        <input type="checkbox" name="repeat_weekdays" value="{{ val }}">{{ label }}
                    </label>
                {% endfor %}
            </span>
            <select name="repeat_range" id="repeat_range_select"
                    style="background-color: #444; color: #aaa;"
                    onchange="document.getElementById('repeat_range_end_group').style.display = (this.value === 'until_date') ? 'inline-block' : 'none';">
                <option value="this_month">This month</option>
                <option value="this_week">This week</option>
                <option value="until_date">Until date…</option>
            </select>
            <span id="repeat_range_end_group" style="display: none;">
                <input type="date" name="repeat_range_end_date" style="background-color: #444; color: #aaa;">
            </span>
```

- [ ] **Step 2.2: Manual UI check**

Start the dev server (replace with the project's actual launch command — see `start.sh`):

```bash
bash start.sh
```

In the browser, open the Schedule tab and verify:
- A `Every day / Every weekday / Every specific weekday` dropdown appears.
- Picking `Every specific weekday` reveals 7 weekday checkboxes; switching back hides them.
- A `This month / This week / Until date…` dropdown appears.
- Picking `Until date…` reveals a date input; switching back hides it.
- Clicking `Add Task` or `Add Daily Task` still works as before (no regression).

Do NOT click `Add Repeat Task` yet — the backend route does not exist; clicking will 404.

- [ ] **Step 2.3: Commit**

```bash
git add templates/schedule_indicate_00.html
git commit -m "Schedule form — add repeat-type, weekday, and range selectors"
```

---

## Task 3: Expansion helper + integration

**Files:**
- Create: `api/repeat_tasks.py`
- Modify: `api/main.py` — both `df_combined` builders (~line 700–810 and ~line 875–984)

- [ ] **Step 3.1: Create the expansion helper**

Create `api/repeat_tasks.py` with:

```python
"""Expand a Schedule template row (is_repeat_task=1) into virtual per-date dicts
that match the daily-task render shape consumed by schedule_indicate_00.html.

Pure functions only — no DB or HTTP — so this can be smoke-checked in a REPL.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable


def parse_weekdays_csv(csv: str | None) -> set[int]:
    """'0,2,4' -> {0, 2, 4}.  Empty / None -> empty set."""
    if not csv:
        return set()
    out: set[int] = set()
    for part in csv.split(","):
        part = part.strip()
        if part.isdigit():
            n = int(part)
            if 0 <= n <= 6:
                out.add(n)
    return out


def date_matches_template(
    d: date,
    repeat_type: str,
    weekdays: set[int],
    range_start: date | None,
    range_end: date | None,
) -> bool:
    if range_start and d < range_start:
        return False
    if range_end and d > range_end:
        return False
    if repeat_type == "every_day":
        return True
    if repeat_type == "every_weekday":
        return d.weekday() < 5  # Mon=0 … Fri=4
    if repeat_type == "every_specific_weekday":
        return d.weekday() in weekdays
    return False


def expand_template(row, visible_dates: Iterable[str]) -> list[dict]:
    """Return one virtual dict per visible date the template matches.

    `row` is a SQLAlchemy Schedule row (or any object with the same attribute
    names). `visible_dates` is the date_sequence already built by the caller —
    we only emit occurrences within the window the UI actually renders.
    """
    weekdays = parse_weekdays_csv(row.repeat_weekdays)
    out: list[dict] = []
    for iso in visible_dates:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        if not date_matches_template(
            d, row.repeat_type or "", weekdays, row.range_start, row.range_end
        ):
            continue
        out.append({
            "id": row.id,
            "name": row.name,
            "link": row.link,
            "start_datetime": None,
            "end_datetime": None,
            "local_start_date": iso,
            "local_start_time": "",
            "local_end_date": iso,
            "local_end_time": "",
            "is_daily_task": 1,        # render with the 🟩 prefix
            "is_repeat_task": 1,       # for future code that needs to distinguish
        })
    return out
```

- [ ] **Step 3.2: Smoke-check the helper in a REPL**

```bash
python -c "
from datetime import date
from api.repeat_tasks import parse_weekdays_csv, date_matches_template
assert parse_weekdays_csv('0,2,4') == {0, 2, 4}
assert parse_weekdays_csv('') == set()
assert parse_weekdays_csv(None) == set()
# every_weekday on a Saturday → False
assert date_matches_template(date(2026, 5, 23), 'every_weekday', set(), None, None) is False
# every_weekday on a Monday → True
assert date_matches_template(date(2026, 5, 25), 'every_weekday', set(), None, None) is True
# every_specific_weekday with Mon+Wed → only those days
assert date_matches_template(date(2026, 5, 25), 'every_specific_weekday', {0, 2}, None, None) is True
assert date_matches_template(date(2026, 5, 26), 'every_specific_weekday', {0, 2}, None, None) is False
# range_end excludes
assert date_matches_template(date(2026, 6, 1), 'every_day', set(), None, date(2026, 5, 31)) is False
print('OK')
"
```

Expected: `OK`. Anything else → fix before continuing.

- [ ] **Step 3.3: Extend the main `/schedule/` builder to expand templates**

In `api/main.py`, in the route that renders `schedule_indicate_00.html` (the one near line 700), update the `tasks` query and the post-processing:

Find the query around line 708:

```python
    tasks = db.query(Schedule).with_entities(
        Schedule.id,
        Schedule.name,
        Schedule.start_datetime,
        Schedule.end_datetime,
        Schedule.link,
        Schedule.is_daily_task,
        Schedule.task_date,
    ).order_by(Schedule.start_datetime).all()
```

Replace with (adds the 5 repeat fields):

```python
    tasks = db.query(Schedule).with_entities(
        Schedule.id,
        Schedule.name,
        Schedule.start_datetime,
        Schedule.end_datetime,
        Schedule.link,
        Schedule.is_daily_task,
        Schedule.task_date,
        Schedule.is_repeat_task,
        Schedule.repeat_type,
        Schedule.repeat_weekdays,
        Schedule.range_start,
        Schedule.range_end,
    ).order_by(Schedule.start_datetime).all()
```

Find the split around line 719:

```python
    regular_tasks = [t for t in tasks if not t.is_daily_task]
    daily_tasks_rows = [t for t in tasks if t.is_daily_task]
```

Replace with (three-way split — repeat templates are neither regular nor daily for display purposes):

```python
    regular_tasks = [t for t in tasks if not t.is_daily_task and not t.is_repeat_task]
    daily_tasks_rows = [t for t in tasks if t.is_daily_task and not t.is_repeat_task]
    repeat_templates = [t for t in tasks if t.is_repeat_task]
```

Find the end of the daily-task append loop (around line 799), just before `length_df_combined = len(df_combined_dict)`. Add this block immediately after the daily-task `for t in daily_tasks_rows:` loop:

```python
    # Expand repeat templates into virtual per-date dicts within the visible window.
    from .repeat_tasks import expand_template  # local import keeps top-of-file tidy
    for t in repeat_templates:
        df_combined_dict.extend(expand_template(t, date_sequence))
```

- [ ] **Step 3.4: Mirror the same changes in the edit-view builder**

In `api/main.py`, in the route that renders `schedule_edit_00.html` (near line 875), apply the same three edits as Step 3.3:
1. Extend the `db.query(Schedule).with_entities(...)` to include the 5 repeat fields (~line 901).
2. Change the two-way split into the same three-way split (~line 911).
3. Append the same `for t in repeat_templates: df_combined_dict.extend(...)` block right after the daily-task append loop (~line 971), with the same `from .repeat_tasks import expand_template` import line.

- [ ] **Step 3.5: Insert a hand-crafted repeat-template row and verify expansion**

Insert a row directly via SQLite to test display without needing Task 4 done yet:

```bash
python -c "
import sqlite3
from datetime import date
c = sqlite3.connect('test.db')
c.execute('''
  INSERT INTO schedules
    (name, link, category, status, start_datetime, end_datetime,
     is_daily_task, task_date,
     is_repeat_task, repeat_type, repeat_weekdays, range_start, range_end)
  VALUES
    ('REPEAT-SMOKE-TEST', NULL, NULL, NULL,
     '2026-05-25 00:00:00', '2026-05-25 00:00:00',
     0, NULL,
     1, 'every_weekday', NULL, '2026-05-25', '2026-05-31')
''')
c.commit()
print('inserted; id row count:', c.execute('SELECT COUNT(*) FROM schedules WHERE name=\"REPEAT-SMOKE-TEST\"').fetchone())
"
```

Restart the dev server and open the Schedule tab. Expected:
- `🟩 REPEAT-SMOKE-TEST` appears on Mon 2026-05-25, Tue 26, Wed 27, Thu 28, Fri 29 — but NOT Sat 30 / Sun 31.
- Existing tasks and daily tasks still render correctly.

- [ ] **Step 3.6: Clean up the smoke-test row**

```bash
python -c "
import sqlite3
c = sqlite3.connect('test.db')
n = c.execute(\"DELETE FROM schedules WHERE name='REPEAT-SMOKE-TEST'\").rowcount
c.commit()
print(f'deleted {n} rows')
"
```

- [ ] **Step 3.7: Commit**

```bash
git add api/repeat_tasks.py api/main.py
git commit -m "Schedule reads — expand repeat templates into per-date virtual rows"
```

---

## Task 4: Backend route — POST /schedule/add_repeat_task/

**Files:**
- Modify: `api/main.py` — add new route directly under `add_daily_task` (~line 1108, after the `RedirectResponse` of that route)

- [ ] **Step 4.1: Add the new route**

Insert this function in `api/main.py` immediately after the `add_daily_task` function's `return RedirectResponse("/schedule/", status_code=303)` line (around line 1108), and BEFORE the `# --------------------` separator comment:

```python
@app.post("/schedule/add_repeat_task/")
async def add_repeat_task(
    request: Request,
    name: str = Form(...),
    date1: str = Form(...),                      # used only as a fallback range_start
    repeat_type: str = Form(...),                # 'every_day' | 'every_weekday' | 'every_specific_weekday'
    repeat_range: str = Form(...),               # 'this_month' | 'this_week' | 'until_date'
    repeat_weekdays: list[str] = Form([]),       # multi-checkbox; empty unless type='every_specific_weekday'
    repeat_range_end_date: str = Form(None),     # required only when repeat_range='until_date'
    link: str = Form(None),
    category: str = Form(None),
    status: str = Form(None),
    db: Session = Depends(get_db),
):
    """Add a Schedule row representing a repeat-task template.

    Stored shape (one row, expanded on read in /schedule/):
      is_repeat_task = 1
      repeat_type    = 'every_day' | 'every_weekday' | 'every_specific_weekday'
      repeat_weekdays = CSV, only when type='every_specific_weekday'
      range_start, range_end = date window
    """
    # range_start: the date the user picked in the form (falls back to today).
    if date1:
        range_start_val = datetime.strptime(date1, "%Y-%m-%d").date()
    else:
        range_start_val = datetime.today().date()

    # range_end: derived from the repeat_range choice.
    if repeat_range == "this_week":
        # End of the week starting Mon → Sun.
        days_until_sun = 6 - range_start_val.weekday()
        range_end_val = range_start_val + timedelta(days=days_until_sun)
    elif repeat_range == "this_month":
        # Last day of the month containing range_start.
        if range_start_val.month == 12:
            first_next = range_start_val.replace(year=range_start_val.year + 1, month=1, day=1)
        else:
            first_next = range_start_val.replace(month=range_start_val.month + 1, day=1)
        range_end_val = first_next - timedelta(days=1)
    elif repeat_range == "until_date":
        if not repeat_range_end_date:
            raise HTTPException(status_code=400, detail="repeat_range_end_date required when repeat_range='until_date'")
        range_end_val = datetime.strptime(repeat_range_end_date, "%Y-%m-%d").date()
    else:
        raise HTTPException(status_code=400, detail=f"unknown repeat_range: {repeat_range!r}")

    # Normalise weekdays: only meaningful for 'every_specific_weekday'.
    weekdays_csv = None
    if repeat_type == "every_specific_weekday":
        valid = [w for w in repeat_weekdays if w in {"0","1","2","3","4","5","6"}]
        if not valid:
            raise HTTPException(status_code=400, detail="every_specific_weekday requires at least one weekday")
        weekdays_csv = ",".join(sorted(set(valid), key=int))

    # NOT NULL sentinel for start/end_datetime.
    sentinel_dt = datetime.combine(range_start_val, datetime.min.time())

    db_item = Schedule(
        name=name,
        link=link,
        category=category,
        status=status,
        start_datetime=sentinel_dt,
        end_datetime=sentinel_dt,
        is_daily_task=0,
        task_date=None,
        is_repeat_task=1,
        repeat_type=repeat_type,
        repeat_weekdays=weekdays_csv,
        range_start=range_start_val,
        range_end=range_end_val,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return RedirectResponse("/schedule/", status_code=303)
```

- [ ] **Step 4.2: Manual end-to-end check — "Every weekday, This week"**

1. Start the dev server: `bash start.sh`
2. Schedule tab → enter `Name = "Standup"`, `Date = today (Mon 2026-05-25)`, leave times default, `Repeat type = Every weekday`, `Range = This week`.
3. Click `Add Repeat Task`.
4. Expected: page reloads; `🟩 Standup` appears Mon–Fri of this week and is absent on Sat/Sun.

- [ ] **Step 4.3: Manual end-to-end check — "Every specific weekday, Until date"**

1. Schedule tab → enter `Name = "Gym"`, `Date = today`, `Repeat type = Every specific weekday`, tick `Mon`, `Wed`, `Fri`, `Range = Until date…`, set end date to one month from today.
2. Click `Add Repeat Task`.
3. Expected: `🟩 Gym` appears on Mon/Wed/Fri of every week up to (and including) the end date; absent on Tue/Thu/weekends.

- [ ] **Step 4.4: Manual end-to-end check — validation**

1. Pick `Repeat type = Every specific weekday`, leave ALL weekday checkboxes unticked, click `Add Repeat Task`.
2. Expected: HTTP 400 with detail `"every_specific_weekday requires at least one weekday"`.
3. Pick `Repeat range = Until date…`, leave the date blank, click `Add Repeat Task`.
4. Expected: HTTP 400 with detail `"repeat_range_end_date required when repeat_range='until_date'"`.

- [ ] **Step 4.5: Clean up the test rows (optional)**

```bash
python -c "
import sqlite3
c = sqlite3.connect('test.db')
for name in ('Standup', 'Gym'):
    n = c.execute('DELETE FROM schedules WHERE name=? AND is_repeat_task=1', (name,)).rowcount
    print(f'{name}: deleted {n}')
c.commit()
"
```

- [ ] **Step 4.6: Commit**

```bash
git add api/main.py
git commit -m "add POST /schedule/add_repeat_task/ route for repeat-task templates"
```

---

## Out of scope (deferred)

- **Editing a repeat template via the existing edit-view route** — clicking a virtual occurrence currently routes to the edit view for the template `id`, but the edit form has no repeat-type / range fields. A future task should branch the edit template on `is_repeat_task` (like it already does on `is_daily_task`) and add the same selectors.
- **Deleting a single occurrence** vs deleting the whole series — out of scope; deleting a template row deletes every visible occurrence.
- **Cross-time-zone correctness for `range_start` / `range_end`** — stored as raw dates (TZ-independent), matching how daily tasks are stored. Acceptable for the project owner's single-TZ workflow.

---

## Self-Review (run before declaring the plan ready)

1. **Spec coverage** — Every locked-in design choice from the prior discussion has a home:
   - Storage = template ✓ (Task 3 expansion)
   - Repeat types: every_day / every_weekday / every_specific_weekday ✓ (Task 2 select, Task 4 validation, Task 3 helper)
   - Weekdays: multi-select, CSV, Mon=0..Sun=6 ✓ (Task 2 checkboxes, Task 3 `parse_weekdays_csv`, Task 4 normalisation)
   - Range: this_month / this_week / until_date ✓ (Task 2 select, Task 4 derivation)
   - Today area shows them like normal/daily tasks ✓ (Task 3 sets `is_daily_task=1` on virtual dicts → existing 🟩 branch fires)
2. **Placeholder scan** — No `TBD` / `handle edge cases` / "similar to" — every step has the actual code or command.
3. **Type consistency** — Field names in `expand_template` output (`local_start_date`, `is_daily_task`, etc.) match the keys produced by the daily-task append loop in `api/main.py:786–799`; column names in Task 1's migration match Task 4's `Schedule(...)` constructor and `api/models.py`'s declarations.

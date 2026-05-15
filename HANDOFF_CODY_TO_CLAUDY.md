# Handoff: Cody to Claudy

Last updated: 2026-05-14 07:03:32 PST

## Purpose
This file records recent work done by Cody so Claudy can continue coding assistance safely without relying on long chat history.

## Project Context
The project is a FastAPI web app with Jinja2 templates, SQLite databases, standalone HTML tools, and a dedicated `translator_on_drawings` package. Main app entry point is `api/main.py`.

The user wants English prompts corrected first, then the requested action performed. Do not edit code unless the user clearly asks for code changes.

## Recent Changes by Cody

### Translator on Drawings
- Fixed Claude batch translation parsing when Claude returns prose plus fenced JSON.
- Accepted both `target` and `english` fields from batch translation JSON.
- Prevented failed translation jobs from forcing progress to `100%`.
- Added safer English overlay rendering:
  - prefers common embedded fonts such as Arial/DejaVu Sans;
  - sanitizes overlay text to plain ASCII to avoid PDF square-box glyphs;
  - sanitizes cached translation hits too.
- Added translator data backup/import tools:
  - download full translator SQLite DB;
  - upload/replace full translator SQLite DB after validation and backup;
  - download glossary as CSV or JSON;
  - upload/upsert glossary CSV or JSON.

Important files:
- `translator_on_drawings/pipeline.py`
- `translator_on_drawings/routes.py`
- `translator_on_drawings/templates/function_translator_on_drawings.html`

Translator data locations:
- Local DB: `data/translator.db`
- Local job files: `data/translator_jobs/`
- Render DB: `/var/data/translator/translator.db`
- Render job files: `/var/data/translator/translator_jobs/`

Notes:
- Input PDFs are temporary and deleted after success/failure.
- Translated PDFs are deleted after download or stale cleanup.
- Extracted Thai phrases and English translations remain cached in `translator.db`.
- With `TRANSLATOR_ENGINE=claude`, extracted text phrases are sent to Anthropic; the full PDF is not intentionally sent.

### Project Function
- Added `not contains` as a row filter operator.
- Added multi-filter support with a maximum of 5 filters.
- Added `AND / OR` join mode for active filters.
- Fixed multi-filter selection so filters are keyed by column index instead of column name. This avoids losing filters when columns are duplicated, blank, or restored oddly.

Important file:
- `templates/project_00.html`

Current filter behavior:
- Shift-click a column tag to add/remove it as a filter.
- Up to 5 filters can be selected.
- `AND` requires all active filters to match.
- `OR` requires any active filter to match.
- Filter state is saved in `sessionStorage`.

## Verification Already Run
- `python -m compileall translator_on_drawings api`
- Route registration was checked for the new translator DB/glossary endpoints.
- Basic translator DB backup/export helper calls were tested.
- Invalid SQLite upload validation was tested.

## Known Risks / Follow-Up
- The Project filter UI has not been browser-tested by Cody after the last index-key fix. Please test Shift-clicking multiple different columns in the browser.
- Translator upload/download DB functions should be tested once in both local and Render environments before relying on them for production backup.
- Existing `data/translator.db` may still contain bad historical cached translations, but rendering now sanitizes them. A future cleanup tool could rewrite or delete polluted rows.
- Translator job access is not strongly tied to the logged-in session/user. If this app is exposed to multiple users, protect job status/download routes.

## Rules for Claudy
- Check `git status --short` and relevant diffs before editing.
- Do not revert Cody’s or the user’s existing changes unless explicitly requested.
- Preserve the current app style and simple Jinja2/FastAPI structure.
- If handing back to Cody, add a short new section below with what Claudy changed and what remains.

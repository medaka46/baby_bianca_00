"""Translator on Drawings — Thai → English construction-drawing translator.

This package contains everything specific to the Translator on Drawings
sub-tab of the Function tab:

- ``pipeline``  — extraction + translation + redact/redraw + job runner
- ``routes``    — FastAPI routes (page, upload, status, download)
- ``templates`` — Jinja2 templates (just one, ``function_translator_on_drawings.html``)

Generic things (the redirect dispatcher in ``/action/``, the World Map and
Periodic Table sub-tabs, base.html) stay in their original locations.
"""

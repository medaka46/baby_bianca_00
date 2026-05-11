"""FastAPI routes for the Translator on Drawings sub-tab.

Self-contained — owns its own Jinja2 environment with two search paths:
  1. ``translator_on_drawings/templates/`` — for ``function_translator_on_drawings.html``
  2. ``templates/`` — for ``base.html`` and any future shared templates

Mounted into the main FastAPI app via ``app.include_router(...)`` in ``api/main.py``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from api.database import ENVIRONMENT
from translator_on_drawings import pipeline as _translator

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Self-contained Jinja2 setup — looks in our local templates/ first, then
# falls back to the project-wide templates/ for base.html.
templates = Jinja2Templates(directory=[
    os.path.join(BASE_DIR, "translator_on_drawings", "templates"),
    os.path.join(BASE_DIR, "templates"),
])
templates.env.globals["ENVIRONMENT"] = ENVIRONMENT

router = APIRouter()


@router.get("/action/translator_on_drawings/")
async def action_translator_on_drawings(request: Request):
    request.session["function_sub_tab_active"] = "translator_on_drawings"
    return templates.TemplateResponse(
        "function_translator_on_drawings.html",
        {
            "request": request,
            "login_username": request.session.get("login_username"),
            "time_zone": request.session.get("time_zone"),
            "tab_page_active": "action",
            "function_sub_tab_active": "translator_on_drawings",
            "today": datetime.today().strftime("%Y-%m-%d"),
        },
    )


@router.post("/action/translator_on_drawings/upload/")
async def translator_upload(request: Request, pdf_file: UploadFile = File(...)):
    """Accept a PDF, save it, kick off the background translation job, return job_id."""
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "Please upload a PDF file."}, status_code=400)
    user_id = request.session.get("id_user")
    job_id = _translator.create_job(pdf_file.filename, user_id)
    file_bytes = await pdf_file.read()
    input_path = _translator.save_uploaded_pdf(job_id, file_bytes)
    _translator.run_job_in_background(job_id, input_path)
    return JSONResponse({"job_id": job_id})


@router.get("/action/translator_on_drawings/status/{job_id}")
async def translator_status(job_id: str):
    job = _translator.get_job(job_id)
    if not job:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    summary = {k: v for k, v in job.items() if k != "mappings"}
    summary["mappings_count"] = len(job.get("mappings", []))
    if job.get("status") == "done":
        summary["mappings"] = job.get("mappings", [])
    return JSONResponse(summary)


@router.get("/action/translator_on_drawings/download/{job_id}")
async def translator_download(job_id: str):
    job = _translator.get_job(job_id)
    if not job or job.get("status") != "done" or not job.get("output_path"):
        return JSONResponse({"error": "Translated file not ready."}, status_code=404)
    if not os.path.exists(job["output_path"]):
        return JSONResponse({"error": "Output file missing on disk."}, status_code=404)
    base = os.path.splitext(job.get("filename") or "translated")[0]
    output_path = job["output_path"]
    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{base}.translated.pdf",
        background=BackgroundTask(
            _translator.remove_output_after_download, job_id, output_path
        ),
    )


@router.get("/action/translator_on_drawings/database/download/")
async def translator_database_download():
    path, filename = _translator.create_database_backup_file()
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(_translator._safe_remove, path),
    )


@router.post("/action/translator_on_drawings/database/upload/")
async def translator_database_upload(database_file: UploadFile = File(...)):
    try:
        result = _translator.replace_database_from_bytes(
            await database_file.read(),
            database_file.filename,
        )
        return JSONResponse({
            "status": "ok",
            "message": "Translator database replaced.",
            "backup_filename": result.get("backup_filename"),
            "database_path": result.get("database_path"),
        })
    except ValueError as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.get("/action/translator_on_drawings/glossary/download/{file_format}")
async def translator_glossary_download(file_format: str):
    try:
        path, filename, media_type = _translator.create_glossary_export_file(file_format)
    except ValueError as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=400)
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(_translator._safe_remove, path),
    )


@router.post("/action/translator_on_drawings/glossary/upload/")
async def translator_glossary_upload(glossary_file: UploadFile = File(...)):
    try:
        result = _translator.import_glossary_from_bytes(
            await glossary_file.read(),
            glossary_file.filename,
        )
        return JSONResponse({
            "status": "ok",
            "message": f"Imported {result['imported']} glossary row(s).",
            "imported": result["imported"],
        })
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=400)
    except ValueError as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

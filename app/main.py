from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
from datetime import datetime

from .database import SessionLocal, engine, Base, get_database_path
from .models import Task

Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def read_tasks(request: Request, db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.id.desc()).all()
    # Check if we're in Render environment for download button visibility
    is_render = bool(os.getenv("RENDER"))
    return templates.TemplateResponse(
        "index.html", {"request": request, "tasks": tasks, "is_render": is_render}
    )


@app.get("/download-db")
def download_database():
    """Download the SQLite database file."""
    db_path = get_database_path()
    
    # Check if database file exists
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"todo_backup_{timestamp}.db"
    
    return FileResponse(
        path=db_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@app.post("/add")
def add_task(title: str = Form(...), db: Session = Depends(get_db)):
    db.add(Task(title=title))
    db.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/toggle/{task_id}")
def toggle_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.completed = not task.completed
    db.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/delete/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse("/", status_code=303)
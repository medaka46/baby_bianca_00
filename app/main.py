from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import shutil
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


@app.post("/upload-db")
async def upload_database(file: UploadFile = File(...)):
    """Upload and replace the SQLite database file."""
    
    # Validate file extension
    if not file.filename.endswith(('.db', '.sqlite', '.sqlite3')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Please upload a SQLite database file (.db, .sqlite, .sqlite3)"
        )
    
    # Get current database path
    db_path = get_database_path()
    
    try:
        # Create backup of current database if it exists
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_path}.backup_{timestamp}"
            shutil.copy2(db_path, backup_path)
        
        # Save uploaded file to database location
        with open(db_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Verify the uploaded file is a valid SQLite database
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            
            # Check if tasks table exists
            has_tasks_table = any(table[0] == 'tasks' for table in tables)
            if not has_tasks_table:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded database does not contain a 'tasks' table"
                )
                
        except sqlite3.Error as e:
            # If validation fails, restore backup if it exists
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, db_path)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid SQLite database file: {str(e)}"
            )
        
        return RedirectResponse("/", status_code=303)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload database: {str(e)}"
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
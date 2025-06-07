from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import shutil
from datetime import datetime

from .database import SessionLocal, engine, Base, get_database_path, get_database_url
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


def recreate_database_engine():
    """Recreate the database engine and session after database replacement."""
    global engine, SessionLocal
    
    # Close all existing connections
    engine.dispose()
    
    # Create new engine with the updated database
    new_database_url = get_database_url()
    engine = create_engine(
        new_database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        echo=True
    )
    
    # Create new session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Ensure tables exist in the new database
    Base.metadata.create_all(bind=engine)
    
    print(f"Database engine recreated with URL: {new_database_url}")


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


@app.get("/debug-info")
def debug_info():
    """Debug endpoint to check environment and paths."""
    db_path = get_database_path()
    is_render = bool(os.getenv("RENDER"))
    
    info = {
        "environment": "Render" if is_render else "Local",
        "database_path": db_path,
        "database_exists": os.path.exists(db_path),
        "database_writable": os.access(os.path.dirname(db_path), os.W_OK) if os.path.exists(os.path.dirname(db_path)) else False,
        "current_working_directory": os.getcwd(),
        "render_env_var": os.getenv("RENDER", "Not set")
    }
    
    if os.path.exists(db_path):
        info["database_size"] = os.path.getsize(db_path)
        
        # Try to read current tasks from database
        try:
            db = SessionLocal()
            task_count = db.query(Task).count()
            tasks = db.query(Task).limit(5).all()
            db.close()
            info["task_count"] = task_count
            info["sample_tasks"] = [{"id": t.id, "title": t.title, "completed": t.completed} for t in tasks]
        except Exception as e:
            info["database_read_error"] = str(e)
    
    return info


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
    backup_path = None  # Initialize backup_path
    
    try:
        # Create backup of current database if it exists
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_path}.backup_{timestamp}"
            shutil.copy2(db_path, backup_path)
            print(f"Created backup: {backup_path}")
        
        # Read uploaded file content
        content = await file.read()
        print(f"Read {len(content)} bytes from uploaded file")
        
        # CRITICAL: Close all existing database connections before replacing file
        print("Closing existing database connections...")
        engine.dispose()
        
        # Save uploaded file to database location
        with open(db_path, "wb") as buffer:
            buffer.write(content)
        print(f"Saved uploaded file to: {db_path}")
        
        # Verify the uploaded file is a valid SQLite database
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            
            print(f"Found tables: {[table[0] for table in tables]}")
            
            # Check if tasks table exists
            has_tasks_table = any(table[0] == 'tasks' for table in tables)
            if not has_tasks_table:
                # Restore backup if validation fails
                if backup_path and os.path.exists(backup_path):
                    shutil.copy2(backup_path, db_path)
                    print(f"Restored backup due to missing tasks table")
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded database does not contain a 'tasks' table"
                )
            
            print("Database validation successful")
            
            # CRITICAL: Recreate the database engine to connect to the new database
            print("Recreating database engine...")
            recreate_database_engine()
            print("Database engine recreated successfully")
                
        except sqlite3.Error as e:
            # If validation fails, restore backup if it exists
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, db_path)
                print(f"Restored backup due to SQLite error: {e}")
                # Recreate engine even after restore
                recreate_database_engine()
            raise HTTPException(
                status_code=400,
                detail=f"Invalid SQLite database file: {str(e)}"
            )
        
        return RedirectResponse("/", status_code=303)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        print(f"Unexpected error during upload: {e}")
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)
            print(f"Restored backup due to unexpected error")
            # Recreate engine after restore
            recreate_database_engine()
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


@app.get("/test-db-connection")
def test_database_connection():
    """Test endpoint to verify database connection and data."""
    try:
        db = SessionLocal()
        
        # Test basic connection
        task_count = db.query(Task).count()
        
        # Get sample tasks
        tasks = db.query(Task).limit(10).all()
        
        db.close()
        
        return {
            "status": "success",
            "message": "Database connection working",
            "task_count": task_count,
            "sample_tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "completed": task.completed
                } for task in tasks
            ],
            "database_path": get_database_path(),
            "database_url": get_database_url()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}",
            "database_path": get_database_path(),
            "database_url": get_database_url()
        }
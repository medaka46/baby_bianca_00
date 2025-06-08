#!/usr/bin/env python3
"""
Simple test server for upload functionality
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import os
import shutil
from datetime import datetime
import sqlite3

app = FastAPI()

def get_database_path():
    """Simple database path function for testing."""
    return "./test_todo.db"

@app.get("/", response_class=HTMLResponse)
def root():
    """Simple HTML page with upload form"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Database Upload Test</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .upload-section { background: #e8f4fd; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .upload-btn { background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            .upload-btn:hover { background: #218838; }
            .file-input { margin: 10px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px; width: 100%; }
            .warning { background: #fff3cd; color: #856404; padding: 10px; border-radius: 4px; margin: 10px 0; }
            .info { background: #d1ecf1; color: #0c5460; padding: 10px; border-radius: 4px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>🧪 Database Upload Test</h1>
        
        <div class="info">
            <strong>Current Database:</strong> """ + get_database_path() + """<br>
            <strong>Exists:</strong> """ + str(os.path.exists(get_database_path())) + """
        </div>
        
        <div class="upload-section">
            <h3>📤 Upload Database</h3>
            <form action="/upload-db" method="post" enctype="multipart/form-data" onsubmit="return confirmUpload()">
                <input type="file" name="file" accept=".db,.sqlite,.sqlite3" class="file-input" required>
                <br>
                <button type="submit" class="upload-btn">📤 Upload & Replace Database</button>
            </form>
            <div class="warning">
                ⚠️ This will replace the current database. A backup will be created automatically.
            </div>
        </div>
        
        <div style="margin-top: 20px;">
            <a href="/debug-info" target="_blank">🔍 Debug Info</a> | 
            <a href="/download-db">💾 Download Current DB</a>
        </div>
        
        <script>
            function confirmUpload() {
                return confirm("Are you sure you want to replace the current database?");
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/debug-info")
def debug_info():
    """Debug endpoint to check environment and paths."""
    db_path = get_database_path()
    
    info = {
        "database_path": db_path,
        "database_exists": os.path.exists(db_path),
        "current_working_directory": os.getcwd(),
    }
    
    if os.path.exists(db_path):
        info["database_size"] = os.path.getsize(db_path)
        
        # Try to read tables
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            info["tables"] = [table[0] for table in tables]
        except Exception as e:
            info["table_error"] = str(e)
    
    return info

@app.post("/upload-db")
async def upload_database(file: UploadFile = File(...)):
    """Upload and replace the SQLite database file."""
    
    print(f"Received file: {file.filename}")
    print(f"Content type: {file.content_type}")
    
    # Validate file extension
    if not file.filename.endswith(('.db', '.sqlite', '.sqlite3')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Please upload a SQLite database file (.db, .sqlite, .sqlite3)"
        )
    
    # Get current database path
    db_path = get_database_path()
    backup_path = None
    
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
        
        # Save uploaded file to database location
        with open(db_path, "wb") as buffer:
            buffer.write(content)
        print(f"Saved uploaded file to: {db_path}")
        
        # Verify the uploaded file is a valid SQLite database
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()
            
            print(f"Found tables: {[table[0] for table in tables]}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Upload successful! ✅",
                    "tables": [table[0] for table in tables],
                    "backup_created": backup_path is not None,
                    "backup_path": backup_path
                }
            )
                
        except sqlite3.Error as e:
            # If validation fails, restore backup if it exists
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, db_path)
                print(f"Restored backup due to SQLite error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid SQLite database file: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error during upload: {e}")
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)
            print(f"Restored backup due to unexpected error")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload database: {str(e)}"
        )

@app.get("/download-db")
def download_database():
    """Download the SQLite database file."""
    from fastapi.responses import FileResponse
    
    db_path = get_database_path()
    
    # Check if database file exists
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_todo_backup_{timestamp}.db"
    
    return FileResponse(
        path=db_path,
        filename=filename,
        media_type="application/octet-stream"
    )

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting simple test server...")
    print("📍 Server will be available at: http://localhost:8002")
    print("🛑 Press Ctrl+C to stop the server")
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="info") 
#!/usr/bin/env python3
"""
Simple test server for upload functionality
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import shutil
from datetime import datetime

app = FastAPI()

def get_database_path():
    """Simple database path function for testing."""
    return "./test_todo.db"

@app.get("/")
def root():
    return {"message": "Test server running"}

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
        import sqlite3
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
                    "message": "Upload successful",
                    "tables": [table[0] for table in tables],
                    "backup_created": backup_path is not None
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 
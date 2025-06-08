from sqlalchemy import create_engine, Column, Integer, String, MetaData, Sequence
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
# from fastapi import FastAPI, Depends, Request, Form, Query, HTTPException


import os

import shutil

def get_database_path():
    """
    Get the appropriate database path based on environment.
    Local: ./test.db (in project directory)
    Render: /var/data/test.db (persistent disk)
    """
    # Check if we're running on Render
    is_render = bool(os.getenv("RENDER"))
    
    if is_render:
        # Render environment - use persistent disk
        data_dir = "/var/data"
        # Ensure the persistent disk directory exists
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "test.db")
        
        # If database doesn't exist on persistent disk, copy from project if available
        project_db_path = os.path.join(os.path.dirname(__file__), '..', 'test.db')
        if not os.path.exists(db_path) and os.path.exists(project_db_path):
            print(f"Copying initial database from {project_db_path} to {db_path}")
            shutil.copy2(project_db_path, db_path)
        
        return db_path
    else:
        # Local development - use project directory
        return os.path.join(os.path.dirname(__file__), '..', 'test.db')

def get_database_url():
    """Get the complete SQLite database URL for SQLAlchemy."""
    db_path = get_database_path()
    return f"sqlite:///{db_path}"

# Get environment information
is_render = bool(os.getenv("RENDER"))
ENVIRONMENT = "production" if is_render else "local"

# Get database configuration
DATABASE_URL = get_database_url()
db_path = get_database_path()

print(f"Environment: {ENVIRONMENT}")
print(f"Database path: {db_path}")
print(f"Database URL: {DATABASE_URL}")
print(f"Database exists: {os.path.exists(db_path)}")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False, "timeout": 30}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# request.session['ENVIRONMENT'] = ENVIRONMENT




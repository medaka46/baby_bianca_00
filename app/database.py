from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

def get_database_path():
    """
    Detect environment and return appropriate database path.
    Local: ./todo.db (current directory)
    Remote (Render): /var/data/todo.db
    """
    # Check if we're in Render environment
    if os.getenv("RENDER"):
        # Render environment - use persistent disk mount path
        data_dir = "/var/data"
    else:
        # Local environment - use current directory
        data_dir = "."
    
    # Ensure directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    return os.path.join(data_dir, "todo.db")

def get_database_url():
    """Get the complete SQLite database URL for SQLAlchemy."""
    db_path = get_database_path()
    return f"sqlite:///{db_path}"

# Get the database URL based on environment
DATABASE_URL = get_database_url()

print(f"Using database: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=True  # Add logging to help debug connection issues
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
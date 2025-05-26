from sqlalchemy import create_engine
from pathlib import Path

DATA_DIR = Path("/data")
DATABASE_URL = f"sqlite:///{DATA_DIR / 'todo.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)
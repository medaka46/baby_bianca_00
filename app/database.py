from pathlib import Path
from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker, declarative_base
import os

# DATA_DIR = Path("/data")
# BASE_DIR = Path(__file__).resolve().parent
# DATABASE_URL = f"sqlite:///{BASE_DIR / 'todo.db'}"
DATABASE_URL = f"sqlite:///{'todo.db'}"



engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
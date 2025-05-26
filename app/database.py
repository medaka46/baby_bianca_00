from sqlalchemy import create_engine
from pathlib import Path

from pathlib import Path 

from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATA_DIR = Path("/data")
DATABASE_URL = f"sqlite:///{DATA_DIR / 'todo.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
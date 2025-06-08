from sqlalchemy import create_engine, Column, Integer, String, MetaData, Sequence
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
# from fastapi import FastAPI, Depends, Request, Form, Query, HTTPException


import os

import shutil

# ----------------
ENVIRONMENT = os.getenv('ENVIRONMENT', 'local')

if ENVIRONMENT == 'production':
    # Path to the existing database file in your project root directory
    # LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '../test_08_db_new_pp.db')
    LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '../test.db')
    # LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '../test_08_db.db')
    # Path to the database file in the /tmp directory
    # TMP_DB_PATH = '/tmp/test_08_db_2.db'
    TMP_DB_PATH = '../test.db'
    # TMP_DB_PATH = '/tmp/test_08_db_2.db'
    
    
    # TMP_DB_PATH = '/tmp/test_08_db_new_pp.db'
    # Copy the database file to /tmp if it doesn't already exist
    if not os.path.exists(TMP_DB_PATH):
        shutil.copyfile(LOCAL_DB_PATH, TMP_DB_PATH)
    DATABASE_URL = f"sqlite:///{TMP_DB_PATH}"
else:
    # Local development database path
    # LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '../test_08_db_new_pp(9).db')
    # LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '../test_08_db_new_pp.db')
    LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '../test.db')
    # LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), '../test_08_db.db')
    DATABASE_URL = f"sqlite:///{LOCAL_DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# request.session['ENVIRONMENT'] = ENVIRONMENT




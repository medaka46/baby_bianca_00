import sqlite3
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from .database import get_database_path, get_database_url

def get_table_names(db_path: str):
    # Using SQLAlchemy to get table names
    engine = create_engine(f"sqlite:///todo.db")
    inspector = inspect(engine)
    return inspector.get_table_names()

# SQLite3 approach (simplest)
def read_with_sqlite3(db_path: str, table_name: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get column names
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Read all rows from selected table
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    # Print results
    print(f"\nColumns: {', '.join(columns)}")
    for row in rows:
        print(f"Row: {row}")
    
    conn.close()

# SQLAlchemy approach (more powerful, already used in your project)
def read_with_sqlalchemy(db_path: str, table_name: str):
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Get column names
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    
    # Read all rows from selected table
    result = session.execute(text(f"SELECT * FROM {table_name}"))
    rows = result.fetchall()
    
    # Print results
    print(f"\nColumns: {', '.join(columns)}")
    for row in rows:
        print(f"Row: {row}")
    
    session.close()

def get_environment_info():
    """Display current environment information."""
    db_path = get_database_path()
    is_render = bool(os.getenv("RENDER"))
    
    print(f"Environment: {'Render (Remote)' if is_render else 'Local'}")
    print(f"Database path: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")
    return db_path

def read_tasks_sqlite3():
    """Read tasks using sqlite3 module."""
    db_path = get_database_path()
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tasks table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        if not cursor.fetchone():
            print("Tasks table does not exist in the database.")
            conn.close()
            return
        
        # Read all tasks
        cursor.execute("SELECT * FROM tasks")
        tasks = cursor.fetchall()
        
        # Print results
        print("\nTasks (using sqlite3):")
        print("ID | Title | Completed")
        print("-" * 50)
        if tasks:
            for task in tasks:
                print(f"{task[0]} | {task[1]} | {task[2]}")
        else:
            print("No tasks found.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")

def read_tasks_sqlalchemy():
    """Read tasks using SQLAlchemy."""
    database_url = get_database_url()
    
    try:
        # Create engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Read all tasks
        result = session.execute(text("SELECT * FROM tasks"))
        tasks = result.fetchall()
        
        # Print results
        print("\nTasks (using SQLAlchemy):")
        print("ID | Title | Completed")
        print("-" * 50)
        if tasks:
            for task in tasks:
                print(f"{task[0]} | {task[1]} | {task[2]}")
        else:
            print("No tasks found.")
        
        session.close()
        
    except Exception as e:
        print(f"SQLAlchemy error: {e}")

if __name__ == "__main__":
    print("SQLite Database Reader")
    print("=" * 50)
    
    # Show environment information
    get_environment_info()
    
    # Replace with your actual database path
    db_path = "test_08_db_2.db"
    
    # Get and display available tables
    tables = get_table_names(db_path)
    print("Available tables:", tables)
    
    # Let user select a table
    table_name = input("\nEnter table name to read: ")
    if table_name not in tables:
        print("Invalid table name!")
        exit(1)
        
    print("\nReading with sqlite3:")
    read_with_sqlite3(db_path, table_name)
    
    print("\nReading with SQLAlchemy:")
    read_with_sqlalchemy(db_path, table_name)

    print("\nReading tasks from todo.db...")
    read_tasks_sqlite3()
    read_tasks_sqlalchemy()
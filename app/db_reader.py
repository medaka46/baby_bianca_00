import sqlite3
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

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

def read_tasks_sqlite3():
    # Connect to the database
    conn = sqlite3.connect("todo.db")
    cursor = conn.cursor()
    
    # Read all tasks
    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()
    
    # Print results
    print("\nTasks from todo.db:")
    print("ID | Title | Completed")
    print("-" * 30)
    for task in tasks:
        print(f"{task[0]} | {task[1]} | {task[2]}")
    
    conn.close()

def read_tasks_sqlalchemy():
    # Create engine and session
    engine = create_engine("sqlite:///todo.db")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Read all tasks
    result = session.execute(text("SELECT * FROM tasks"))
    tasks = result.fetchall()
    
    # Print results
    print("\nTasks from todo.db (SQLAlchemy):")
    print("ID | Title | Completed")
    print("-" * 30)
    for task in tasks:
        print(f"{task[0]} | {task[1]} | {task[2]}")
    
    session.close()

if __name__ == "__main__":
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
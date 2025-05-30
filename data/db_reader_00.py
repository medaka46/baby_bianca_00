import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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
    print("Reading tasks from todo.db...")
    read_tasks_sqlite3()
    read_tasks_sqlalchemy()
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def read_tasks_sqlite3():
    # Connect to the database
    conn = sqlite3.connect("todo.db")
    cursor = conn.cursor()
    
    # Read all tasks
    cursor.execute("SELECT * FROM schedules")
    tasks = cursor.fetchall()
    
    # Print results
    print("\nTasks from todo.db:")
    print("ID | Title | Completed")
    print("-" * 30)
    for task in tasks:
        print(f"{task[0]} | {task[1]} | {task[2]} | {task[3]} | {task[4]}")
    
    conn.close()

def read_tasks_sqlalchemy():
    # Create engine and session
    engine = create_engine(f"sqlite:///{db_name}")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Read all tasks
    result = session.execute(text("SELECT * FROM schedules"))
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
    db_name = input('Please key in db name!')
    # read_tasks_sqlite3()
    read_tasks_sqlalchemy()
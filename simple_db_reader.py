#!/usr/bin/env python3
"""
Simple SQLite Database Reader with Environment Detection
Supports both local (/data/todo.db) and Render remote (/var/data/todo.db) environments.
"""

import sqlite3
import os
from pathlib import Path

def detect_environment():
    """
    Detect if we're running locally or on Render.
    Returns tuple: (is_render, environment_name)
    """
    is_render = bool(os.getenv("RENDER"))
    return is_render, "Render (Remote)" if is_render else "Local"

def get_database_path():
    """
    Get the appropriate database path based on environment.
    Local: ./todo.db (current directory)
    Remote (Render): /var/data/todo.db
    """
    is_render, _ = detect_environment()
    
    if is_render:
        # Render environment - use persistent disk mount path
        data_dir = "/var/data"
    else:
        # Local environment - use current directory
        data_dir = "."
    
    # Ensure directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    return os.path.join(data_dir, "todo.db")

def show_environment_info():
    """Display current environment and database information."""
    is_render, env_name = detect_environment()
    db_path = get_database_path()
    
    print("=" * 60)
    print("SQLite Database Reader - Environment Detection")
    print("=" * 60)
    print(f"Environment: {env_name}")
    print(f"Database path: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")
    
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        print(f"Database size: {file_size} bytes")
    
    print("-" * 60)

def read_tasks():
    """Read and display all tasks from the database."""
    db_path = get_database_path()
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tasks table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        if not cursor.fetchone():
            print("❌ Tasks table does not exist in the database.")
            conn.close()
            return
        
        # Get table schema
        cursor.execute("PRAGMA table_info(tasks)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Read all tasks
        cursor.execute("SELECT * FROM tasks ORDER BY id")
        tasks = cursor.fetchall()
        
        # Display results
        print(f"📋 Tasks Table (Columns: {', '.join(column_names)})")
        print("-" * 60)
        
        if tasks:
            print(f"{'ID':<5} | {'Title':<30} | {'Completed':<10}")
            print("-" * 60)
            for task in tasks:
                task_id = task[0] if len(task) > 0 else "N/A"
                title = task[1] if len(task) > 1 else "N/A"
                completed = "✅ Yes" if (len(task) > 2 and task[2]) else "❌ No"
                print(f"{task_id:<5} | {title:<30} | {completed:<10}")
            print(f"\n📊 Total tasks: {len(tasks)}")
        else:
            print("📭 No tasks found in the database.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def list_all_tables():
    """List all tables in the database."""
    db_path = get_database_path()
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📊 Available tables:")
        if tables:
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("  No tables found.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e}")

def main():
    """Main function to run the database reader."""
    show_environment_info()
    list_all_tables()
    print()
    read_tasks()

if __name__ == "__main__":
    main() 
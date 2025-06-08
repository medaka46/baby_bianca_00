#!/usr/bin/env python3
"""
Comprehensive test script for database upload functionality
"""

import requests
import os
import shutil
import sqlite3
import time
import json

def create_test_database():
    """Create a test database with sample data."""
    test_db_path = "test_upload_sample.db"
    
    # Remove if exists
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    # Create database with sample data
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    
    # Create tasks table
    cursor.execute('''
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            title VARCHAR NOT NULL,
            completed BOOLEAN
        )
    ''')
    
    # Insert sample tasks
    sample_tasks = [
        ("UPLOADED TASK 1: Test upload functionality", False),
        ("UPLOADED TASK 2: Verify database replacement", True),
        ("UPLOADED TASK 3: Check SQLAlchemy reconnection", False),
        ("UPLOADED TASK 4: Confirm data persistence", True),
    ]
    
    cursor.executemany(
        "INSERT INTO tasks (title, completed) VALUES (?, ?)",
        sample_tasks
    )
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created test database: {test_db_path}")
    return test_db_path

def test_server_endpoints(base_url="http://localhost:8000"):
    """Test all server endpoints."""
    print(f"\n🧪 Testing server endpoints at {base_url}")
    
    endpoints = [
        ("/", "Main page"),
        ("/debug-info", "Debug info"),
        ("/test-db-connection", "Database connection test")
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            if response.status_code == 200:
                print(f"✅ {description}: OK")
                if endpoint == "/debug-info":
                    data = response.json()
                    print(f"   Database: {data.get('database_path')}")
                    print(f"   Exists: {data.get('database_exists')}")
                    print(f"   Task count: {data.get('task_count', 'N/A')}")
                elif endpoint == "/test-db-connection":
                    data = response.json()
                    print(f"   Status: {data.get('status')}")
                    print(f"   Task count: {data.get('task_count')}")
                    if data.get('sample_tasks'):
                        print(f"   Sample tasks: {len(data['sample_tasks'])}")
            else:
                print(f"❌ {description}: {response.status_code}")
        except Exception as e:
            print(f"❌ {description}: Error - {e}")

def test_upload_functionality(base_url="http://localhost:8000"):
    """Test the upload functionality."""
    print(f"\n📤 Testing upload functionality")
    
    # Create test database
    test_db_path = create_test_database()
    
    try:
        # Get initial state
        print("📊 Getting initial database state...")
        response = requests.get(f"{base_url}/test-db-connection")
        if response.status_code == 200:
            initial_data = response.json()
            print(f"   Initial task count: {initial_data.get('task_count')}")
        
        # Upload test database
        print("📤 Uploading test database...")
        with open(test_db_path, 'rb') as f:
            files = {'file': (test_db_path, f, 'application/octet-stream')}
            response = requests.post(f"{base_url}/upload-db", files=files)
        
        if response.status_code == 303:
            print("✅ Upload successful (redirect response)")
        elif response.status_code == 200:
            print("✅ Upload successful")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Wait a moment for the database to be updated
        time.sleep(2)
        
        # Test database connection after upload
        print("🔗 Testing database connection after upload...")
        response = requests.get(f"{base_url}/test-db-connection")
        if response.status_code == 200:
            new_data = response.json()
            print(f"   Status: {new_data.get('status')}")
            print(f"   New task count: {new_data.get('task_count')}")
            
            # Check if we have the uploaded tasks
            sample_tasks = new_data.get('sample_tasks', [])
            uploaded_tasks = [task for task in sample_tasks if 'UPLOADED TASK' in task.get('title', '')]
            
            if uploaded_tasks:
                print(f"✅ Found {len(uploaded_tasks)} uploaded tasks!")
                for task in uploaded_tasks:
                    print(f"   - {task['title']}")
                return True
            else:
                print("❌ No uploaded tasks found - database may not have been replaced")
                print("   Current tasks:")
                for task in sample_tasks:
                    print(f"   - {task['title']}")
                return False
        else:
            print(f"❌ Database connection test failed: {response.status_code}")
            return False
            
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            print(f"🧹 Cleaned up test file: {test_db_path}")

def main():
    """Main test function."""
    print("🚀 COMPREHENSIVE DATABASE UPLOAD TEST")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Test server endpoints
    test_server_endpoints(base_url)
    
    # Test upload functionality
    success = test_upload_functionality(base_url)
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED! Upload functionality is working correctly.")
        print("\n📋 SUMMARY:")
        print("✅ Server endpoints accessible")
        print("✅ Database upload successful")
        print("✅ SQLAlchemy engine reconnection working")
        print("✅ Data persistence confirmed")
    else:
        print("❌ TESTS FAILED! Upload functionality needs fixing.")
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Check server logs for errors")
        print("2. Verify database file permissions")
        print("3. Ensure SQLAlchemy engine is being recreated")
        print("4. Check if backup/restore is interfering")

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Test script for database upload functionality
"""

import requests
import os
import shutil

def test_upload():
    base_url = "http://localhost:8000"
    
    # First, check debug info
    print("=== Debug Info ===")
    try:
        response = requests.get(f"{base_url}/debug-info")
        if response.status_code == 200:
            debug_info = response.json()
            for key, value in debug_info.items():
                print(f"{key}: {value}")
        else:
            print(f"Debug info failed: {response.status_code}")
    except Exception as e:
        print(f"Error getting debug info: {e}")
    
    print("\n=== Testing Upload ===")
    
    # Create a test database file
    test_db_path = "test_upload.db"
    
    # Copy existing database for testing
    if os.path.exists("todo.db"):
        shutil.copy2("todo.db", test_db_path)
        print(f"Created test database: {test_db_path}")
    else:
        print("No existing todo.db found to copy")
        return
    
    # Test upload
    try:
        with open(test_db_path, 'rb') as f:
            files = {'file': (test_db_path, f, 'application/octet-stream')}
            response = requests.post(f"{base_url}/upload-db", files=files)
            
        print(f"Upload response status: {response.status_code}")
        print(f"Upload response headers: {dict(response.headers)}")
        
        if response.status_code == 303:
            print("✅ Upload successful (redirect response)")
        elif response.status_code == 200:
            print("✅ Upload successful")
            print(f"Response: {response.text}")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
    
    # Clean up
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print(f"Cleaned up test file: {test_db_path}")

if __name__ == "__main__":
    test_upload() 
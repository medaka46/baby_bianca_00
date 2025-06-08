#!/usr/bin/env python3
"""
Simple server startup script
"""

import sys
import os
import uvicorn

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def start_server():
    """Start the FastAPI server"""
    try:
        # Import the app
        from app.main import app
        
        print("🚀 Starting FastAPI server...")
        print("📍 Server will be available at: http://localhost:8000")
        print("📊 Debug info: http://localhost:8000/debug-info")
        print("📤 Upload test: http://localhost:8000/upload-db")
        print("🛑 Press Ctrl+C to stop the server")
        print("-" * 50)
        
        # Start the server
        uvicorn.run(
            app, 
            host="127.0.0.1", 
            port=8000, 
            log_level="info",
            reload=True
        )
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're in the correct directory and all dependencies are installed.")
    except Exception as e:
        print(f"❌ Server error: {e}")

if __name__ == "__main__":
    start_server() 
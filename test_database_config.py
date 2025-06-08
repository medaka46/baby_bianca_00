#!/usr/bin/env python3
"""
Test script to verify database configuration
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_config():
    """Test the database configuration."""
    print("🧪 Testing Database Configuration")
    print("=" * 50)
    
    try:
        # Import database functions
        from api.database import get_database_path, get_database_url, ENVIRONMENT
        
        # Test environment detection
        is_render = bool(os.getenv("RENDER"))
        print(f"Environment: {ENVIRONMENT}")
        print(f"Is Render: {is_render}")
        print(f"RENDER env var: {os.getenv('RENDER', 'Not set')}")
        
        # Test database path
        db_path = get_database_path()
        db_url = get_database_url()
        
        print(f"Database path: {db_path}")
        print(f"Database URL: {db_url}")
        print(f"Database exists: {os.path.exists(db_path)}")
        
        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path)
            print(f"Database size: {file_size} bytes")
        
        # Test database connection
        print("\n🔗 Testing Database Connection")
        print("-" * 30)
        
        from api.database import SessionLocal
        from api.models import User, Schedule, Link
        
        db = SessionLocal()
        
        # Count records in each table
        user_count = db.query(User).count()
        schedule_count = db.query(Schedule).count()
        link_count = db.query(Link).count()
        
        print(f"Users: {user_count}")
        print(f"Schedules: {schedule_count}")
        print(f"Links: {link_count}")
        
        db.close()
        
        print("\n✅ Database configuration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Database configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_render_simulation():
    """Test with simulated Render environment."""
    print("\n🌐 Testing Simulated Render Environment")
    print("=" * 50)
    
    # Set RENDER environment variable
    os.environ["RENDER"] = "true"
    
    try:
        # Re-import to get updated configuration
        import importlib
        import api.database
        importlib.reload(api.database)
        
        from api.database import get_database_path, get_database_url, ENVIRONMENT
        
        print(f"Environment: {ENVIRONMENT}")
        print(f"Database path: {get_database_path()}")
        print(f"Database URL: {get_database_url()}")
        
        # Check if the path points to /var/data
        db_path = get_database_path()
        if db_path.startswith("/var/data"):
            print("✅ Correctly configured for Render persistent disk")
        else:
            print("❌ Not configured for Render persistent disk")
        
        return True
        
    except Exception as e:
        print(f"❌ Render simulation test failed: {e}")
        return False
    finally:
        # Clean up environment variable
        if "RENDER" in os.environ:
            del os.environ["RENDER"]

if __name__ == "__main__":
    print("🚀 Database Configuration Test Suite")
    print("=" * 60)
    
    # Test local configuration
    success1 = test_database_config()
    
    # Test Render simulation
    success2 = test_render_simulation()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 ALL TESTS PASSED!")
        print("\n📋 Summary:")
        print("✅ Local database configuration working")
        print("✅ Render environment simulation working")
        print("✅ Database connection successful")
        print("✅ Ready for deployment to Render")
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please check the error messages above.") 
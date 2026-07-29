import os
import sys
import uvicorn

# Setup Python paths for root and backend
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "fewa-v3-backend")

sys.path.insert(0, root_dir)
sys.path.insert(0, backend_dir)

# Set environment variables for testing infrastructure if not already set
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5433")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault("POSTGRES_DB", "fewa_test_db")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6380")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9002")
os.environ.setdefault("MINIO_ACCESS_KEY", "miniotestadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "miniotestpassword")
os.environ.setdefault("MINIO_BUCKET_WACZ", "fewa-wacz-test-storage")
os.environ.setdefault("SECRET_KEY", "test-secret-key-super-secure-key-32chars-min!")

if __name__ == "__main__":
    print("🚀 Starting FEWA Backend Server via main.py...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

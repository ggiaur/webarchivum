"""Session-wide test environment. Runs at collection time (before any test
module imports app.core.config), so these env vars are what Settings()
actually picks up — pointing DB/Redis-backed API tests at the same isolated
test containers test_archive_crud.py already uses, not production defaults.
"""

import os

os.environ.setdefault("POSTGRES_PORT", "5460")
os.environ.setdefault("POSTGRES_USER", "fewa_admin")
os.environ.setdefault("POSTGRES_PASSWORD", "fewa_dev_local_only")
os.environ.setdefault("POSTGRES_DB", "fewa_v3")
os.environ.setdefault("REDIS_PORT", "6380")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9002")
os.environ.setdefault("MINIO_ACCESS_KEY", "miniotestadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "miniotestpassword")

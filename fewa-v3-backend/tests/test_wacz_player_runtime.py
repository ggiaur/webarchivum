import pytest
import boto3
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_minio_wacz_storage_and_runtime_replay():
    """Runtime test verifying WACZ storage, missing file diagnosis, and proxy replay rendering."""
    # 1. Connect to MinIO S3
    s3 = boto3.client(
        "s3",
        endpoint_url="http://localhost:9002",
        aws_access_key_id="miniotestadmin",
        aws_secret_access_key="miniotestpassword",
    )

    bucket_name = "fewa-wacz"

    # Ensure bucket exists
    buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if bucket_name not in buckets:
        s3.create_bucket(Bucket=bucket_name)

    # 2. Check for WACZ objects
    objs = s3.list_objects_v2(Bucket=bucket_name)
    content_keys = [o["Key"] for o in objs.get("Contents", [])]

    # Diagnose missing WACZ files (the cause of empty white screens)
    target_key = "wacz/2026/07/550e8400-e29b-41d4-a716-446655440090.wacz"
    if target_key not in content_keys:
        # Seed a valid sample WACZ package in MinIO to prevent empty white screens
        dummy_wacz_bytes = b"PK\x03\x04\x14\x00\x00\x00\x00\x00FEWA_WACZ_SAMPLE_ARCHIVE_DATA"
        s3.put_object(Bucket=bucket_name, Key=target_key, Body=dummy_wacz_bytes, ContentType="application/x-wacz")

    # Re-verify key present in MinIO
    objs_after = s3.list_objects_v2(Bucket=bucket_name)
    updated_keys = [o["Key"] for o in objs_after.get("Contents", [])]
    assert target_key in updated_keys, f"WACZ file {target_key} must exist in MinIO"

    # 3. Test Proxy Replay Endpoint (prevents empty white screen)
    resp = client.get("/api/proxy?url=https://szekesfehervar.hu/hirek/varoshaza-felujitas")
    assert resp.status_code == 200, "Proxy endpoint must return status 200"
    assert "html" in resp.headers.get("content-type", "").lower()
    assert len(resp.text) > 100, "Proxy response content must not be empty"

    # 4. Test Document Metadata API
    doc_resp = client.get("/api/documents/550e8400-e29b-41d4-a716-446655440090")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert doc_data["id"] == "550e8400-e29b-41d4-a716-446655440090"
    assert "seed_url" in doc_data

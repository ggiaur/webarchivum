import io
import pytest
from unittest.mock import MagicMock, patch
from app.core.minio_client import MinIOClient


def test_minio_client_init():
    with patch("boto3.client") as mock_boto:
        client = MinIOClient()
        assert client.bucket_wacz == "fewa-wacz"
        mock_boto.assert_called_once()


def test_minio_upload_stream_sha256():
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        client = MinIOClient()
        test_data = b"FEWA test WACZ file content"
        stream = io.BytesIO(test_data)

        res = client.upload_wacz_stream("test/file.wacz", stream)

        assert res["filesize_bytes"] == len(test_data)
        assert len(res["sha256"]) == 64
        assert res["minio_path"] == "test/file.wacz"
        mock_s3.put_object.assert_called_once()


def test_minio_health_check_success():
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_s3.list_buckets.return_value = {"Buckets": []}
        mock_boto.return_value = mock_s3

        client = MinIOClient()
        assert client.check_health() is True

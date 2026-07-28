import logging
import hashlib
from typing import Optional, BinaryIO
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)


class MinIOClient:
    def __init__(self):
        endpoint_url = f"http{'s' if settings.MINIO_SECURE else ''}://{settings.MINIO_ENDPOINT}"
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self.bucket_wacz = settings.MINIO_BUCKET_WACZ

    def ensure_bucket_exists(self) -> None:
        """Ensures WACZ bucket exists."""
        try:
            self.client.head_bucket(Bucket=self.bucket_wacz)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["404", "NoSuchBucket"]:
                logger.info(f"Creating MinIO bucket: {self.bucket_wacz}")
                self.client.create_bucket(Bucket=self.bucket_wacz)
            else:
                raise e

    def upload_wacz_stream(
        self,
        key: str,
        data: BinaryIO,
        content_type: str = "application/x-wacz",
    ) -> dict:
        """
        Uploads WACZ stream to MinIO and returns file metadata including SHA-256 and size.
        """
        sha256_hash = hashlib.sha256()
        size = 0
        data.seek(0)
        while chunk := data.read(8192):
            sha256_hash.update(chunk)
            size += len(chunk)

        data.seek(0)
        calculated_sha256 = sha256_hash.hexdigest()

        self.client.put_object(
            Bucket=self.bucket_wacz,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": calculated_sha256},
        )

        return {
            "minio_path": key,
            "sha256": calculated_sha256,
            "filesize_bytes": size,
            "bucket": self.bucket_wacz,
        }

    def check_health(self) -> bool:
        try:
            self.client.list_buckets()
            return True
        except Exception as e:
            logger.warning(f"MinIO health check failed: {e}")
            return False


minio_client = MinIOClient()

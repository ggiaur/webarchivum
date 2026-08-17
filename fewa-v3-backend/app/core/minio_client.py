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
        self.ensure_bucket_exists()
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

    def generate_presigned_wacz_url(self, key: str, expires_in: int = 3600) -> str:
        """A presigned MinIO URL, valid only where MINIO_ENDPOINT itself is
        reachable — i.e. server-side callers, NOT end-user browsers.

        This is deliberately no longer used for ReplayWeb.page's `source`.
        The concern this function's old docstring flagged ("MINIO_ENDPOINT
        must be resolvable from the end user's browser") became a real
        outage on 2026-08-02: it emitted http://localhost:9002/..., which
        from a user's browser means THEIR machine, and is mixed content on
        an https:// page besides. Replay now goes through the API's own
        same-origin /api/wacz/{id} route (see app/api/v1/search.py), which
        uses get_wacz_object below."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_wacz, "Key": key},
            ExpiresIn=expires_in,
        )

    def get_wacz_object(self, key: str, range_header: Optional[str] = None) -> dict:
        """Fetches a WACZ object, passing an HTTP Range header straight
        through to MinIO when present.

        Range support is required, not optional: ReplayWeb.page treats a
        WACZ as a remote zip and requests individual entries by byte range
        rather than downloading the whole (often hundreds of MB) archive.
        Returns the raw boto3 response so the caller can stream Body and
        mirror ContentRange/ContentLength back to the browser."""
        params = {"Bucket": self.bucket_wacz, "Key": key}
        if range_header:
            params["Range"] = range_header
        return self.client.get_object(**params)

    def check_health(self) -> bool:
        try:
            self.client.list_buckets()
            return True
        except Exception as e:
            logger.warning(f"MinIO health check failed: {e}")
            return False


minio_client = MinIOClient()

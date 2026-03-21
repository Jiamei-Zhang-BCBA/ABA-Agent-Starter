"""
VaultService — tenant-isolated object storage operations.
Supports both local filesystem (dev) and MinIO/S3 (prod) backends.
Enforces _config.md rules: no tree-external folders, append fault-tolerance, etc.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Allowed top-level directories (from _config.md)
ALLOWED_DIRECTORIES = {
    "00-RawData", "01-Clients", "02-Sessions",
    "03-Staff", "04-Supervision", "05-Communication", "06-Templates",
}


def _validate_path(path: str) -> None:
    """Enforce _config.md directory rules: no tree-external top-level folders."""
    parts = path.strip("/").split("/")
    if parts and parts[0] not in ALLOWED_DIRECTORIES:
        raise ValueError(
            f"Path '{path}' is outside the allowed directory tree. "
            f"Allowed top-level directories: {ALLOWED_DIRECTORIES}"
        )


# ---------------------------------------------------------------------------
# Local filesystem implementation
# ---------------------------------------------------------------------------

class LocalVaultService:
    """Tenant-isolated vault operations backed by local filesystem."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.base = Path(settings.local_storage_path) / "tenants" / tenant_id

    def _vault_path(self, path: str) -> Path:
        return self.base / "vault" / path

    def read_file(self, path: str) -> Optional[str]:
        """Read a file from the tenant's vault. Returns None if not found."""
        fp = self._vault_path(path)
        if not fp.exists():
            return None
        return fp.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        """Write (create or overwrite) a file in the tenant's vault."""
        _validate_path(path)
        fp = self._vault_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")

    def append_file(self, path: str, content: str) -> None:
        """
        Append content to a file. If file doesn't exist, create it with
        a skeleton header first (enforcing _config.md append fault-tolerance).
        """
        _validate_path(path)
        existing = self.read_file(path)

        if existing is None:
            filename = path.rsplit("/", 1)[-1].replace(".md", "")
            skeleton = f"# {filename}\n\n"
            existing = skeleton
            logger.info("Auto-created missing file: %s", path)

        merged = existing.rstrip("\n") + "\n\n" + content.strip() + "\n"
        self.write_file(path, merged)

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in the tenant's vault."""
        return self._vault_path(path).exists()

    def list_directory(self, path: str) -> list[str]:
        """List items under a directory in the tenant's vault."""
        dp = self._vault_path(path)
        if not dp.exists():
            return []
        return [item.name for item in dp.iterdir()]

    def upload_raw_file(self, upload_path: str, file_bytes: bytes, content_type: str) -> None:
        """Upload a raw file (not vault-structured) for processing."""
        fp = self.base / "uploads" / upload_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(file_bytes)

    def read_raw_file(self, upload_path: str) -> bytes:
        """Read a raw uploaded file."""
        fp = self.base / "uploads" / upload_path
        return fp.read_bytes()

    def write_delivery(self, job_id: str, filename: str, content: bytes, content_type: str) -> str:
        """Write a delivery file and return its storage path."""
        rel = f"deliveries/{job_id}/{filename}"
        fp = self.base / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(content)
        return str(fp)

    def get_delivery_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Return the local file path as a 'URL' for local dev."""
        return f"file://{storage_path}"


# ---------------------------------------------------------------------------
# S3/MinIO implementation
# ---------------------------------------------------------------------------

def _get_s3_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
    )


def _tenant_key(tenant_id: str, path: str) -> str:
    """Build the S3 key for a tenant-scoped path."""
    return f"tenants/{tenant_id}/vault/{path}"


class VaultService:
    """Tenant-isolated vault operations backed by S3/MinIO."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.client = _get_s3_client()
        self.bucket = settings.minio_bucket

    def _key(self, path: str) -> str:
        return _tenant_key(self.tenant_id, path)

    def read_file(self, path: str) -> Optional[str]:
        """Read a file from the tenant's vault. Returns None if not found."""
        from botocore.exceptions import ClientError
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._key(path))
            return resp["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def write_file(self, path: str, content: str) -> None:
        """Write (create or overwrite) a file in the tenant's vault."""
        _validate_path(path)
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._key(path),
            Body=content.encode("utf-8"),
            ContentType="text/markdown; charset=utf-8",
        )

    def append_file(self, path: str, content: str) -> None:
        """
        Append content to a file. If file doesn't exist, create it with
        a skeleton header first (enforcing _config.md append fault-tolerance).
        """
        _validate_path(path)
        existing = self.read_file(path)

        if existing is None:
            filename = path.rsplit("/", 1)[-1].replace(".md", "")
            skeleton = f"# {filename}\n\n"
            existing = skeleton
            logger.info("Auto-created missing file: %s", path)

        merged = existing.rstrip("\n") + "\n\n" + content.strip() + "\n"
        self.write_file(path, merged)

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in the tenant's vault."""
        from botocore.exceptions import ClientError
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except ClientError:
            return False

    def list_directory(self, path: str) -> list[str]:
        """List objects under a prefix in the tenant's vault."""
        prefix = self._key(path.rstrip("/") + "/")
        resp = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix,
            Delimiter="/",
        )
        items = []
        for cp in resp.get("CommonPrefixes", []):
            items.append(cp["Prefix"].removeprefix(prefix).rstrip("/"))
        for obj in resp.get("Contents", []):
            items.append(obj["Key"].removeprefix(prefix))
        return items

    def upload_raw_file(self, upload_path: str, file_bytes: bytes, content_type: str) -> None:
        """Upload a raw file (not vault-structured) for processing."""
        key = f"tenants/{self.tenant_id}/uploads/{upload_path}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )

    def read_raw_file(self, upload_path: str) -> bytes:
        """Read a raw uploaded file."""
        key = f"tenants/{self.tenant_id}/uploads/{upload_path}"
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def write_delivery(self, job_id: str, filename: str, content: bytes, content_type: str) -> str:
        """Write a delivery file and return its storage path."""
        key = f"tenants/{self.tenant_id}/deliveries/{job_id}/{filename}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return key

    def get_delivery_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a delivery."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": storage_path},
            ExpiresIn=expires_in,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_vault_service(tenant_id: str) -> LocalVaultService | VaultService:
    """Return the appropriate vault service based on settings.storage_mode."""
    if settings.storage_mode == "local":
        return LocalVaultService(tenant_id)
    return VaultService(tenant_id)

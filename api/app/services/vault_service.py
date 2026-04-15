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
        fp = (self.base / "vault" / path).resolve()
        jail = (self.base / "vault").resolve()
        if not str(fp).startswith(str(jail) + os.sep) and fp != jail:
            raise ValueError(f"Path escapes vault jail: {path}")
        return fp

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

    def list_directory(self, path: str) -> list[dict[str, str]]:
        """List items under a directory with type information."""
        dp = self._vault_path(path)
        if not dp.exists():
            return []
        items = []
        for item in sorted(dp.iterdir(), key=lambda p: (p.is_file(), p.name)):
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": f"{path.rstrip('/')}/{item.name}",
            })
        return items

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

    def list_directory(self, path: str) -> list[dict[str, str]]:
        """List objects under a prefix with type information."""
        prefix = self._key(path.rstrip("/") + "/")
        resp = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix,
            Delimiter="/",
        )
        items = []
        for cp in resp.get("CommonPrefixes", []):
            name = cp["Prefix"].removeprefix(prefix).rstrip("/")
            if name:
                items.append({
                    "name": name,
                    "type": "directory",
                    "path": f"{path.rstrip('/')}/{name}",
                })
        for obj in resp.get("Contents", []):
            name = obj["Key"].removeprefix(prefix)
            if name:
                items.append({
                    "name": name,
                    "type": "file",
                    "path": f"{path.rstrip('/')}/{name}",
                })
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
# Client vault initialization
# ---------------------------------------------------------------------------

def init_client_vault(vault: "LocalVaultService | VaultService", code: str) -> None:
    """Create standard vault directories for a new client."""
    skeleton = {
        f"01-Clients/Client-{code}/Client-{code}-核心档案.md": (
            f"---\ntags: [个案/核心档案]\nchild_alias: {code}\n"
            f"archive_status: 🟡 激活（初访完成，待正式评估）\n---\n\n"
            f"# [[Client-{code}-核心档案]]\n\n"
            f"**档案代号**：Client-{code}\n"
            f"**档案状态**：🟡 激活\n\n"
            f"## 👤 基本背景\n\n| 项目 | 内容 |\n|------|------|\n| **儿童昵称** | {code} |\n\n"
            f"## 📋 当前目标摘要\n\n> [待评估后填写]\n\n"
            f"## 📝 变更日志\n\n- 建档\n"
        ),
        f"02-Sessions/Client-{code}-日志库/README.md": (
            f"# Client-{code} 日志库\n\n此目录存放该个案的课后记录和干预日志。\n"
        ),
        f"05-Communication/Client-{code}/README.md": (
            f"# Client-{code} 家校沟通\n\n此目录存放家书、家长反馈等沟通文件。\n"
        ),
    }
    for path, content in skeleton.items():
        if not vault.file_exists(path):
            vault.write_file(path, content)


# ---------------------------------------------------------------------------
# Write skill output to vault
# ---------------------------------------------------------------------------

def write_output_to_vault(
    vault: "LocalVaultService | VaultService",
    skill_name: str,
    client_code: str,
    content: str,
) -> None:
    """
    Write skill output to the appropriate vault location.
    Supports multi-file output via <!-- FILE: path --> markers.
    Called by both job_processor (auto-approve) and review_service (manual approve).
    """
    import re
    from datetime import datetime, timezone

    # Check if output contains multi-file markers
    file_markers = list(re.finditer(
        r'<!--\s*FILE:\s*(.+?)(?:\s*\|\s*(APPEND))?\s*-->', content
    ))

    if file_markers:
        for i, marker in enumerate(file_markers):
            path = marker.group(1).strip()
            is_append = marker.group(2) is not None
            start = marker.end()
            end = file_markers[i + 1].start() if i + 1 < len(file_markers) else len(content)
            file_content = content[start:end].strip()

            if not file_content:
                continue

            try:
                if is_append:
                    existing = vault.read_file(path) or ""
                    vault.write_file(path, existing + "\n" + file_content)
                else:
                    vault.write_file(path, file_content)
                logger.info("Wrote vault file: %s (append=%s)", path, is_append)
            except Exception as e:
                logger.error("Failed to write vault file %s: %s", path, e)
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path_map = {
            "session-reviewer": f"02-Sessions/Client-{client_code}-日志库/{today}-反馈.md",
            "parent-update": f"05-Communication/Client-{client_code}/{today}-家书.md",
            "teacher-guide": f"03-Staff/{today}-实操单-Client-{client_code}.md",
            "quick-summary": f"05-Communication/Client-{client_code}/{today}-简报.md",
            "staff-supervision": f"04-Supervision/{today}-听课反馈.md",
            "clinical-reflection": f"04-Supervision/{today}-周复盘.md",
            "reinforcer-tracker": f"01-Clients/Client-{client_code}/{today}-强化物评估.md",
            "privacy-filter": f"00-RawData/脱敏存档/{today}-Client-{client_code}-脱敏.md",
            "staff-onboarding": f"03-Staff/{today}-新教师建档.md",
            "intake-interview": f"01-Clients/Client-{client_code}/Client-{client_code}-初访信息表.md",
            "profile-builder": f"01-Clients/Client-{client_code}/Client-{client_code}-核心档案.md",
            "plan-generator": f"01-Clients/Client-{client_code}/{today}-IEP.md",
            "fba-analyzer": f"01-Clients/Client-{client_code}/{today}-FBA.md",
            "assessment-logger": f"01-Clients/Client-{client_code}/{today}-评估记录.md",
            "milestone-report": f"01-Clients/Client-{client_code}/{today}-阶段报告.md",
            "transfer-protocol": f"01-Clients/Client-{client_code}/{today}-移交协议.md",
        }
        path = path_map.get(skill_name)
        if path:
            vault.write_file(path, content)
            logger.info("Wrote vault file: %s", path)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_vault_service(tenant_id: str) -> LocalVaultService | VaultService:
    """Return the appropriate vault service based on settings.storage_mode."""
    if settings.storage_mode == "local":
        return LocalVaultService(tenant_id)
    return VaultService(tenant_id)

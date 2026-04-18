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
    """
    Create the full vault directory tree for a new client,
    matching the structure defined in skills/_config.md.

    Directories created:
      01-Clients/Client-{code}/          — 个案主目录
      02-Sessions/Client-{code}-日志库/  — 课后记录
      05-Communication/Client-{code}-沟通记录/ — 家校沟通
    """
    c = f"Client-{code}"

    skeleton = {
        # ── 01-Clients: 核心档案（完整骨架，含所有受保护章节锚点）
        f"01-Clients/{c}/{c}-核心档案.md": (
            f"---\ntags: [个案/核心档案]\nchild_alias: {code}\n"
            f"archive_status: 🟡 激活（初访完成，待正式评估）\n---\n\n"
            f"# [[{c}-核心档案]]\n\n"
            f"**档案代号**：{c}\n"
            f"**档案状态**：🟡 激活\n\n"
            f"## 👤 基本背景\n\n"
            f"| 项目 | 内容 |\n|------|------|\n"
            f"| **儿童昵称** | {code} |\n"
            f"| **性别** | ⏳ [待填写] |\n"
            f"| **出生日期** | ⏳ [待填写] |\n"
            f"| **诊断** | ⏳ [待填写] |\n\n"
            f"## 🧠 核心能力画像\n\n> ⏳ [待 assessment-logger 评估后填写]\n\n"
            f"## 🎁 强化物偏好清单\n\n> ⏳ [待 reinforcer-tracker 评估后填写]\n\n"
            f"## ⚠️ 历史问题行为备忘\n\n> ⏳ [待 fba-analyzer 分析后填写]\n\n"
            f"## 📋 当前目标摘要\n\n> ⏳ [待 plan-generator 制定IEP后填写]\n\n"
            f"## 🔗 全生命周期索引\n\n"
            f"- [[{c}-初访信息表]]\n\n"
            f"## 📝 变更日志\n\n"
            f"- 建档\n"
        ),

        # ── 01-Clients: 初访信息表占位
        f"01-Clients/{c}/{c}-初访信息表.md": (
            f"# [[{c}-初访信息表]]\n\n"
            f"> ⏳ 此文件将在 intake-interview 技能执行后自动填充。\n"
        ),

        # ── 01-Clients: 能力评估占位
        f"01-Clients/{c}/{c}-能力评估.md": (
            f"# [[{c}-能力评估]]\n\n"
            f"> ⏳ 此文件将在 assessment-logger 技能执行后自动填充。\n"
        ),

        # ── 01-Clients: FBA分析占位
        f"01-Clients/{c}/{c}-FBA分析.md": (
            f"# [[{c}-FBA分析]]\n\n"
            f"> ⏳ 此文件将在 fba-analyzer 技能执行后自动填充。\n"
        ),

        # ── 01-Clients: IEP方案占位
        f"01-Clients/{c}/{c}-IEP.md": (
            f"# [[{c}-IEP]]\n\n"
            f"> ⏳ 此文件将在 plan-generator 技能执行后自动填充。\n"
        ),

        # ── 02-Sessions: 日志库目录
        f"02-Sessions/{c}-日志库/README.md": (
            f"# {c} 日志库\n\n"
            f"此目录存放该个案的课后记录和干预日志。\n"
            f"由 session-reviewer 技能自动生成。\n"
        ),

        # ── 05-Communication: 沟通记录目录
        f"05-Communication/{c}-沟通记录/README.md": (
            f"# {c} 家校沟通\n\n"
            f"此目录存放家书、家长反馈、电梯简报等沟通文件。\n"
            f"由 parent-update / quick-summary / milestone-report 技能自动生成。\n"
        ),
    }

    for path, content in skeleton.items():
        if not vault.file_exists(path):
            vault.write_file(path, content)


# ---------------------------------------------------------------------------
# Markdown section replacement helper (BUG #19)
# ---------------------------------------------------------------------------

def _normalize_section_key(raw: str) -> str:
    """
    Normalize a section identifier for fuzzy matching.
    Strips emoji, punctuation, whitespace; keeps Chinese/English/digit characters.
    Mirrors the rule from skills/_config.md:
      'matching ignores emoji and surrounding whitespace, compares Chinese keyword only.'
    """
    import re as _re
    # Keep CJK, latin letters, digits; drop everything else (emoji/symbols/spaces).
    cleaned = _re.sub(
        r"[^0-9A-Za-z\u4e00-\u9fff]+", "", raw or "",
    )
    return cleaned.lower()


def _replace_markdown_section(
    doc: str, section_name: str, new_body: str,
) -> str:
    """
    Replace the contents of a markdown section whose heading (any level ##/###/####)
    matches `section_name` (emoji-insensitive). Keeps the original heading line,
    swaps the body up to the next heading of same-or-higher level.

    If `new_body` itself starts with a heading that normalizes to the same key,
    that heading is dropped (we reuse the original) to avoid duplicated titles.

    If no matching section is found, the new content is appended at the end of the
    document under a fresh `## {section_name}` heading — never dropped.
    """
    import re as _re

    target = _normalize_section_key(section_name)
    if not target:
        # Degenerate: no meaningful keyword; fall back to appending at EOF.
        return doc.rstrip() + "\n\n" + new_body.strip() + "\n"

    lines = doc.splitlines()
    heading_re = _re.compile(r"^(#{2,6})\s+(.+?)\s*$")

    # Find the matching heading line
    start_idx = -1
    start_level = 0
    for idx, line in enumerate(lines):
        m = heading_re.match(line)
        if not m:
            continue
        level = len(m.group(1))
        if _normalize_section_key(m.group(2)) == target:
            start_idx = idx
            start_level = level
            break

    # Strip a leading duplicate heading from new_body. AI frequently echoes the
    # section title followed by extra annotations like "（基于 2026-04-22 FBA 更新）".
    # We treat it as duplicate if the normalized heading contains the target key
    # OR the target key contains the heading (prefix match in either direction).
    body = new_body.strip()
    body_lines = body.splitlines()
    if body_lines:
        m0 = heading_re.match(body_lines[0])
        if m0:
            heading_key = _normalize_section_key(m0.group(2))
            if heading_key and (target in heading_key or heading_key in target):
                body = "\n".join(body_lines[1:]).lstrip("\n")

    if start_idx == -1:
        # Section not found — append a fresh one so data is never lost.
        sep = "" if doc.endswith("\n\n") else ("\n" if doc.endswith("\n") else "\n\n")
        return (
            doc.rstrip()
            + "\n\n## "
            + section_name.strip()
            + "\n\n"
            + body.strip()
            + "\n"
        )

    # Find the end: next heading with level <= start_level
    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        m = heading_re.match(lines[idx])
        if m and len(m.group(1)) <= start_level:
            end_idx = idx
            break

    new_lines = (
        lines[: start_idx + 1]
        + [""]
        + body.splitlines()
        + [""]
        + lines[end_idx:]
    )
    return "\n".join(new_lines)


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

    # Check if output contains multi-file markers.
    # BUG #19 fix: support APPEND / EDIT:section / MERGE operation modifiers.
    # BUG #21 fix: also accept SECTION_REPLACE:<section> and REPLACE_SECTION:<section>
    # / APPEND_SECTION:<section> synonyms produced by skill prompts. They are all
    # canonicalized onto the EDIT branch (section-aware replace) or APPEND branch
    # so the regex group captures correctly instead of leaking the modifier into
    # the path group.
    file_markers = list(re.finditer(
        r'<!--\s*FILE:\s*([^|>]+?)\s*'
        r'(?:\|\s*('
        r'APPEND(?:_SECTION:[^>]+?)?'  # APPEND  |  APPEND_SECTION:<name>
        r'|EDIT:[^>]+?'
        r'|SECTION_REPLACE:[^>]+?'
        r'|REPLACE_SECTION:[^>]+?'
        r'|MERGE'
        r')\s*)?-->',
        content,
    ))

    if file_markers:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i, marker in enumerate(file_markers):
            path = marker.group(1).strip()
            op_raw = (marker.group(2) or "").strip()
            op_upper = op_raw.upper()
            # Normalize op into (op_name, op_arg).
            # Accept synonyms so skill prompts can use EDIT / SECTION_REPLACE /
            # REPLACE_SECTION interchangeably without leaking into the path group.
            if op_upper == "APPEND":
                op_name, op_arg = "APPEND", None
            elif op_upper.startswith("APPEND_SECTION:"):
                # APPEND_SECTION:<name> — append under a specific section; treat as
                # plain APPEND for now (section-targeted append needs a dedicated
                # handler; defer to a later fix).
                op_name, op_arg = "APPEND", None
            elif op_upper.startswith("EDIT:"):
                op_name = "EDIT"
                op_arg = op_raw[len("EDIT:"):].strip()
            elif op_upper.startswith("SECTION_REPLACE:"):
                op_name = "EDIT"
                op_arg = op_raw[len("SECTION_REPLACE:"):].strip()
            elif op_upper.startswith("REPLACE_SECTION:"):
                op_name = "EDIT"
                op_arg = op_raw[len("REPLACE_SECTION:"):].strip()
            elif op_upper == "MERGE":
                # Short-term: treat MERGE as APPEND to avoid data loss. A proper
                # semantic merge needs section-aware parsing; defer to a later fix.
                op_name, op_arg = "APPEND", None
            else:
                op_name, op_arg = "WRITE", None
            is_append = op_name == "APPEND"
            is_edit = op_name == "EDIT"
            edit_section = op_arg
            start = marker.end()
            end = file_markers[i + 1].start() if i + 1 < len(file_markers) else len(content)
            file_content = content[start:end].strip()

            if not file_content:
                continue

            # Normalize placeholders that Claude may have left literal.
            # e.g. "01-Clients/Client-[代号]/Client-[代号]-xxx.md" → real code
            if client_code:
                path = (
                    path
                    .replace("[代号]", client_code)
                    .replace("[儿童代号]", client_code)
                    .replace("[儿童昵称]", client_code)
                    .replace("{code}", client_code)
                    .replace("{{代号}}", client_code)
                )
            path = (
                path
                .replace("{{当前日期}}", today)
                .replace("[当前日期]", today)
                .replace("{today}", today)
            )

            # Guard: if the path still points to a *different* client folder than the bound
            # client_code (e.g. Claude insisted on "Client-Demo-乐乐" from the upload body),
            # rewrite it onto the bound client's folder to protect data isolation.
            if client_code:
                expected_prefix = f"Client-{client_code}"
                # Look for any 01-Clients/Client-xxx/ segment and rewrite it
                m = re.match(r'^(01-Clients/)(Client-[^/]+)(/.*)$', path)
                if m and m.group(2) != expected_prefix:
                    wrong = m.group(2)
                    # Replace the folder and any occurrences of the wrong prefix in the filename
                    new_path = f"{m.group(1)}{expected_prefix}{m.group(3)}".replace(
                        wrong, expected_prefix
                    )
                    logger.warning(
                        "Path rewrite: '%s' → '%s' (client binding enforced)",
                        path, new_path,
                    )
                    path = new_path
                    # ALSO rewrite wikilinks and inline references in the file content
                    # so Obsidian links don't break. (BUG #11)
                    file_content = file_content.replace(wrong, expected_prefix)

            try:
                if is_append:
                    existing = vault.read_file(path) or ""
                    vault.write_file(path, existing + "\n" + file_content)
                elif is_edit and edit_section:
                    # Replace a single section in an existing markdown file.
                    # Section matching rules (per skills/_config.md):
                    #   - ignore leading emoji and surrounding whitespace
                    #   - match on the core Chinese/English keyword substring
                    existing = vault.read_file(path) or ""
                    if not existing:
                        # No file yet — degrade gracefully by writing the new
                        # content as a fresh file rather than dropping data.
                        vault.write_file(path, file_content)
                        logger.info(
                            "EDIT target missing, wrote as new file: %s", path,
                        )
                    else:
                        new_doc = _replace_markdown_section(
                            existing, edit_section, file_content,
                        )
                        vault.write_file(path, new_doc)
                        logger.info(
                            "Edited section '%s' in vault file: %s",
                            edit_section, path,
                        )
                else:
                    vault.write_file(path, file_content)
                logger.info(
                    "Wrote vault file: %s (op=%s)", path, op_name,
                )
            except Exception as e:
                logger.error("Failed to write vault file %s: %s", path, e)
    else:
        # Skills that legitimately operate without a client_code (no individual case)
        _CLIENT_OPTIONAL_SKILLS = {
            "privacy-filter",      # may run before any client exists
            "staff-onboarding",
            "staff-supervision",
            "clinical-reflection",
        }

        if not client_code and skill_name not in _CLIENT_OPTIONAL_SKILLS:
            # Refuse to write garbage paths like "Client--xxx.md" when no client is bound.
            # Surface the problem to the caller via log so it doesn't silently land as delivered.
            logger.warning(
                "write_output_to_vault: skill=%s requires client_code but none provided; skipping write",
                skill_name,
            )
            return

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # When a client is bound, build the prefix; otherwise leave a no-client tag.
        c = f"Client-{client_code}" if client_code else "Client-未指定"
        path_map = {
            # 00-RawData
            "privacy-filter": f"00-RawData/脱敏存档/{c}-脱敏原始数据.md",
            # 01-Clients — 固定名称文件（覆盖占位骨架）
            "intake-interview": f"01-Clients/{c}/{c}-初访信息表.md",
            "profile-builder": f"01-Clients/{c}/{c}-核心档案.md",
            "assessment-logger": f"01-Clients/{c}/{c}-能力评估.md",
            "fba-analyzer": f"01-Clients/{c}/{c}-FBA分析.md",
            "plan-generator": f"01-Clients/{c}/{c}-IEP.md",
            # 01-Clients — 带日期的文件（可多版本）
            "reinforcer-tracker": f"01-Clients/{c}/{c}-强化物评估-{today}.md",
            "milestone-report": f"01-Clients/{c}/{c}-里程碑报告-{today}.md",
            "transfer-protocol": f"01-Clients/{c}/{c}-转衔移交协议-{today}.md",
            # 02-Sessions
            "session-reviewer": f"02-Sessions/{c}-日志库/{today}-{c}-记录.md",
            # 03-Staff
            "teacher-guide": f"03-Staff/{today}-实操单-{c}.md",
            "staff-onboarding": f"03-Staff/{today}-新教师建档.md",
            "staff-supervision": f"04-Supervision/{today}-听课反馈.md",
            # 04-Supervision
            "clinical-reflection": f"04-Supervision/{today}-周复盘.md",
            # 05-Communication
            "parent-update": f"05-Communication/{c}-沟通记录/{today}-家书.md",
            "quick-summary": f"05-Communication/{c}-沟通记录/{today}-电梯简报.md",
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

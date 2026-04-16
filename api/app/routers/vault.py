"""Vault file browsing endpoints — read, download, tree, write."""

import logging
import re as re_mod

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.client import Client, ClientUserLink
from app.services.auth_service import get_current_user, require_roles
from app.services.vault_service import create_vault_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vault", tags=["vault"])

# Role-based directory access
_ROLE_DIRS: dict[str, set[str]] = {
    UserRole.ORG_ADMIN.value: {
        "00-RawData", "01-Clients", "02-Sessions",
        "03-Staff", "04-Supervision", "05-Communication", "06-Templates",
    },
    UserRole.BCBA.value: {
        "01-Clients", "02-Sessions", "03-Staff",
        "04-Supervision", "05-Communication",
    },
    UserRole.TEACHER.value: {"02-Sessions", "05-Communication"},
    UserRole.PARENT.value: {"05-Communication"},
}

# Roles that need client-level filtering
_CLIENT_FILTERED_ROLES = {UserRole.TEACHER.value, UserRole.PARENT.value}


def _extract_client_code(path: str) -> str | None:
    """Extract client code_name from vault path like '01-Clients/Client-A-乐乐/...'."""
    match = re_mod.search(r"Client-([^/]+)", path)
    return match.group(1) if match else None


async def _get_user_linked_codes(db: AsyncSession, user: User) -> set[str]:
    """Get all client code_names linked to a teacher/parent user."""
    stmt = (
        select(Client.code_name)
        .join(ClientUserLink, Client.id == ClientUserLink.client_id)
        .where(
            Client.tenant_id == str(user.tenant_id),
            ClientUserLink.user_id == str(user.id),
        )
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


async def _check_vault_access(user: User, path: str, db: AsyncSession | None = None) -> None:
    """Verify user has access to the requested vault path (role + client level)."""
    clean = path.strip("/").replace("\\", "/")

    # Block path traversal
    if ".." in clean:
        raise HTTPException(status_code=400, detail="非法路径")

    parts = clean.split("/")
    if not parts:
        raise HTTPException(status_code=400, detail="路径不能为空")

    top_dir = parts[0]
    allowed = _ROLE_DIRS.get(user.role, set())
    if top_dir not in allowed:
        raise HTTPException(status_code=403, detail="无权访问此目录")

    # Client-level filtering for teacher/parent
    if user.role in _CLIENT_FILTERED_ROLES and db is not None:
        client_code = _extract_client_code(clean)
        if client_code:
            linked_codes = await _get_user_linked_codes(db, user)
            if client_code not in linked_codes:
                raise HTTPException(status_code=403, detail="无权访问该个案文件")


@router.get("/read")
async def read_vault_file(
    path: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read a vault file's content (Markdown text)."""
    await _check_vault_access(user, path, db)

    vault = create_vault_service(str(user.tenant_id))
    content = vault.read_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    return {"path": path, "content": content}


@router.get("/download")
async def download_vault_file(
    path: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a vault file as raw bytes."""
    await _check_vault_access(user, path, db)

    vault = create_vault_service(str(user.tenant_id))
    content = vault.read_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    raw_name = path.rsplit("/", 1)[-1]
    safe_name = re_mod.sub(r'[^\w\u4e00-\u9fff.\-]', '_', raw_name)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/tree")
async def list_vault_tree(
    prefix: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List files and directories under a vault path with type information."""
    await _check_vault_access(user, prefix, db)

    vault = create_vault_service(str(user.tenant_id))
    items = vault.list_directory(prefix)
    # Filter out hidden files and placeholders
    items = [
        item for item in items
        if not item["name"].startswith(".") and item["name"] != "placeholder.md"
    ]

    # For teacher/parent: filter directory listing to only show linked clients
    if user.role in _CLIENT_FILTERED_ROLES:
        linked_codes = await _get_user_linked_codes(db, user)
        filtered = []
        for item in items:
            code = _extract_client_code(item["name"])
            if code is None or code in linked_codes:
                filtered.append(item)
        items = filtered

    return {"prefix": prefix, "items": items}


# Root directory metadata
_ROOT_INFO: dict[str, dict[str, str]] = {
    "00-RawData": {"label": "原始数据", "icon": "database"},
    "01-Clients": {"label": "个案档案", "icon": "users"},
    "02-Sessions": {"label": "课后记录", "icon": "clipboard"},
    "03-Staff": {"label": "师资管理", "icon": "user-check"},
    "04-Supervision": {"label": "督导复盘", "icon": "book-open"},
    "05-Communication": {"label": "家校沟通", "icon": "message-square"},
    "06-Templates": {"label": "模板库", "icon": "file-text"},
}


@router.get("/roots")
async def list_vault_roots(
    user: User = Depends(get_current_user),
):
    """List root directories accessible to the current user based on role."""
    allowed = _ROLE_DIRS.get(user.role, set())
    roots = [
        {
            "path": dir_name,
            "label": _ROOT_INFO[dir_name]["label"],
            "icon": _ROOT_INFO[dir_name]["icon"],
        }
        for dir_name in sorted(allowed)
        if dir_name in _ROOT_INFO
    ]
    return {"roots": roots}


# ---------------------------------------------------------------------------
# Write (update existing file) — restricted to supervisors
# ---------------------------------------------------------------------------

class VaultWriteRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., max_length=5_000_000)


@router.put("/write")
async def write_vault_file(
    req: VaultWriteRequest,
    user: User = Depends(require_roles("org_admin", "bcba")),
    db: AsyncSession = Depends(get_db),
):
    """Write content to an existing vault file. Only supervisors can write."""
    await _check_vault_access(user, req.path, db)

    vault = create_vault_service(str(user.tenant_id))

    # Only allow updating existing files, not creating new ones
    if not vault.file_exists(req.path):
        raise HTTPException(status_code=404, detail="文件不存在，无法通过此接口创建新文件")

    vault.write_file(req.path, req.content)
    logger.info("Vault file updated by %s: %s", user.name, req.path)

    return {"path": req.path, "message": "文件已更新"}

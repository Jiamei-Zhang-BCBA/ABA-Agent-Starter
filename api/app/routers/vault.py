"""Vault file browsing endpoints — read, download, tree."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.models.user import User, UserRole
from app.services.auth_service import get_current_user
from app.services.vault_service import create_vault_service

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


def _check_vault_access(user: User, path: str) -> None:
    """Verify user has access to the requested vault path."""
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


@router.get("/read")
async def read_vault_file(
    path: str = Query(...),
    user: User = Depends(get_current_user),
):
    """Read a vault file's content (Markdown text)."""
    _check_vault_access(user, path)

    vault = create_vault_service(str(user.tenant_id))
    content = vault.read_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    return {"path": path, "content": content}


@router.get("/download")
async def download_vault_file(
    path: str = Query(...),
    user: User = Depends(get_current_user),
):
    """Download a vault file as raw bytes."""
    _check_vault_access(user, path)

    vault = create_vault_service(str(user.tenant_id))
    content = vault.read_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    filename = path.rsplit("/", 1)[-1]
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tree")
async def list_vault_tree(
    prefix: str = Query(...),
    user: User = Depends(get_current_user),
):
    """List files under a vault directory prefix."""
    _check_vault_access(user, prefix)

    vault = create_vault_service(str(user.tenant_id))
    files = vault.list_directory(prefix)
    # Filter out hidden files and placeholders
    files = [f for f in files if not f.startswith(".") and f != "placeholder.md"]

    return {"prefix": prefix, "files": files}

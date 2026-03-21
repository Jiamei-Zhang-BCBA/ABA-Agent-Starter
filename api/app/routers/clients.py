"""Client and Staff management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.job import Job, JobStatus
from app.models.client import Client
from app.schemas.client import ClientCreateRequest, ClientResponse, StaffResponse
from app.services.auth_service import get_current_user, require_roles

router = APIRouter(prefix="/api/v1", tags=["clients"])


@router.get("/clients")
async def list_clients(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all clients for the current tenant."""
    stmt = select(Client).where(Client.tenant_id == user.tenant_id)

    # Teachers/parents only see linked clients
    if user.role in (UserRole.TEACHER, UserRole.PARENT):
        from app.models.client import ClientUserLink
        stmt = (
            select(Client)
            .join(ClientUserLink, ClientUserLink.client_id == Client.id)
            .where(ClientUserLink.user_id == user.id)
        )

    result = await db.execute(stmt)
    clients = result.scalars().all()
    return {"clients": [ClientResponse.model_validate(c) for c in clients]}


@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    req: ClientCreateRequest,
    user: User = Depends(require_roles("org_admin", "bcba")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new client (child) record."""
    client = Client(
        tenant_id=user.tenant_id,
        code_name=req.code_name,
        display_alias=req.display_alias,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    # Initialize vault directories for this client
    from app.services.vault_service import create_vault_service
    vault = create_vault_service(str(user.tenant_id))
    code = req.code_name
    for path in [
        f"01-Clients/Client-{code}/placeholder.md",
        f"02-Sessions/Client-{code}-日志库/placeholder.md",
        f"05-Communication/Client-{code}/placeholder.md",
    ]:
        if not vault.file_exists(path):
            vault.write_file(path, f"# {path.rsplit('/', 1)[0]}\n")

    return client


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific client."""
    stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/clients/{client_id}/timeline")
async def get_client_timeline(
    client_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the full workflow timeline for a client.
    Returns all completed/reviewed jobs with outputs, ordered chronologically.
    Also returns vault file listing for this client.
    """
    # Verify client access
    stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get all jobs for this client
    stmt = (
        select(Job)
        .where(and_(Job.client_id == client_id, Job.tenant_id == user.tenant_id))
        .order_by(Job.created_at.desc())
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    # Get submitter names
    from app.models.user import User as UserModel
    user_ids = list({j.user_id for j in jobs})
    user_map = {}
    if user_ids:
        u_result = await db.execute(select(UserModel).where(UserModel.id.in_(user_ids)))
        for u in u_result.scalars().all():
            user_map[u.id] = u.name

    # Build timeline entries
    timeline = []
    for j in jobs:
        entry = {
            "job_id": j.id,
            "feature_id": j.feature_id,
            "status": j.status,
            "submitted_by": user_map.get(j.user_id, "未知"),
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "has_output": j.output_content is not None and len(j.output_content or "") > 0,
        }
        # Include output for delivered/approved jobs
        if j.status in (JobStatus.DELIVERED.value, JobStatus.APPROVED.value):
            entry["output_content"] = j.output_content
        timeline.append(entry)

    # Get vault files for this client
    from app.services.vault_service import create_vault_service
    vault = create_vault_service(str(user.tenant_id))
    code = client.code_name

    vault_files = {}
    vault_dirs = {
        "档案": f"01-Clients/Client-{code}",
        "日志": f"02-Sessions/Client-{code}-日志库",
        "沟通": f"05-Communication/Client-{code}",
    }
    for label, path in vault_dirs.items():
        try:
            files = vault.list_directory(path)
            vault_files[label] = [f for f in files if f != "placeholder.md"]
        except Exception:
            vault_files[label] = []

    return {
        "client": ClientResponse.model_validate(client),
        "timeline": timeline,
        "vault_files": vault_files,
        "total_jobs": len(jobs),
        "completed_jobs": sum(1 for j in jobs if j.status in (JobStatus.DELIVERED.value, JobStatus.APPROVED.value)),
    }


@router.get("/staff")
async def list_staff(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List staff (teachers + BCBAs) for the current tenant."""
    stmt = select(User).where(
        User.tenant_id == user.tenant_id,
        User.role.in_([UserRole.TEACHER, UserRole.BCBA]),
    )
    result = await db.execute(stmt)
    staff = result.scalars().all()
    return {"staff": [StaffResponse.model_validate(s) for s in staff]}

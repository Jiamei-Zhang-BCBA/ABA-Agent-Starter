"""Client and Staff management endpoints."""

import logging
import uuid

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.job import Job, JobStatus
from app.models.client import Client, ClientUserLink
from app.schemas.client import (
    ClientCreateRequest,
    ClientResponse,
    StaffResponse,
    ClientAssignRequest,
    ClientAssignmentResponse,
)
from app.services.auth_service import get_current_user, require_roles

router = APIRouter(prefix="/api/v1", tags=["clients"])

# Vault directories visible per role
_VAULT_DIRS_SUPERVISOR = {
    "档案": "01-Clients/Client-{code}",
    "日志": "02-Sessions/Client-{code}-日志库",
    "沟通": "05-Communication/Client-{code}-沟通记录",
}
_VAULT_DIRS_TEACHER = {
    "日志": "02-Sessions/Client-{code}-日志库",
    "沟通": "05-Communication/Client-{code}-沟通记录",
}


async def _check_client_link(
    db: AsyncSession, client_id: str, user: User,
) -> None:
    """For teachers/parents, verify they are linked to this client."""
    if user.role in (UserRole.TEACHER.value, UserRole.PARENT.value):
        stmt = select(ClientUserLink).where(
            ClientUserLink.client_id == client_id,
            ClientUserLink.user_id == user.id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="无权访问该个案")


# ---------------------------------------------------------------------------
# Client CRUD
# ---------------------------------------------------------------------------

@router.get("/clients")
async def list_clients(
    teacher_id: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List clients. Teachers/parents see only linked clients.
    Supervisors can optionally filter by teacher_id."""
    if user.role in (UserRole.TEACHER.value, UserRole.PARENT.value):
        # Teachers/parents only see their own linked clients
        stmt = (
            select(Client)
            .join(ClientUserLink, ClientUserLink.client_id == Client.id)
            .where(
                Client.tenant_id == user.tenant_id,
                ClientUserLink.user_id == user.id,
            )
        )
    elif teacher_id:
        # Supervisor filtering by a specific teacher
        stmt = (
            select(Client)
            .join(ClientUserLink, ClientUserLink.client_id == Client.id)
            .where(
                Client.tenant_id == user.tenant_id,
                ClientUserLink.user_id == teacher_id,
                ClientUserLink.relation == "teacher",
            )
        )
    else:
        stmt = select(Client).where(Client.tenant_id == user.tenant_id)

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
    try:
        from app.services.vault_service import create_vault_service, init_client_vault
        vault = create_vault_service(str(user.tenant_id))
        init_client_vault(vault, req.code_name)
    except Exception:
        logger.exception("Failed to initialize vault for client %s", req.code_name)

    return client


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific client. Teachers/parents must be linked."""
    stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    await _check_client_link(db, client_id, user)
    return client


@router.get("/clients/{client_id}/timeline")
async def get_client_timeline(
    client_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get timeline + vault files for a client. Vault dirs are filtered by role."""
    # Verify client exists in tenant
    stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    await _check_client_link(db, client_id, user)

    # Jobs
    stmt = (
        select(Job)
        .where(and_(Job.client_id == client_id, Job.tenant_id == user.tenant_id))
        .order_by(Job.created_at.desc())
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    # Submitter names
    from app.models.user import User as UserModel
    user_ids = list({j.user_id for j in jobs})
    user_map = {}
    if user_ids:
        u_result = await db.execute(select(UserModel).where(UserModel.id.in_(user_ids)))
        for u in u_result.scalars().all():
            user_map[u.id] = u.name

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
        if j.status in (JobStatus.DELIVERED.value, JobStatus.APPROVED.value):
            entry["output_content"] = j.output_content
        timeline.append(entry)

    # Vault files — role-based filtering
    from app.services.vault_service import create_vault_service
    vault = create_vault_service(str(user.tenant_id))
    code = client.code_name

    is_supervisor = user.role in (UserRole.ORG_ADMIN.value, UserRole.BCBA.value)
    dirs = _VAULT_DIRS_SUPERVISOR if is_supervisor else _VAULT_DIRS_TEACHER

    vault_files = {}
    for label, path_tpl in dirs.items():
        dir_path = path_tpl.format(code=code)
        try:
            items = vault.list_directory(dir_path)
            vault_files[label] = [
                {"name": item["name"], "path": item["path"]}
                for item in items
                if item["name"] not in ("placeholder.md", ".gitkeep", "README.md")
                and item["type"] == "file"
            ]
        except Exception:
            vault_files[label] = []

    return {
        "client": ClientResponse.model_validate(client),
        "timeline": timeline,
        "vault_files": vault_files,
        "total_jobs": len(jobs),
        "completed_jobs": sum(1 for j in jobs if j.status in (JobStatus.DELIVERED.value, JobStatus.APPROVED.value)),
    }


# ---------------------------------------------------------------------------
# Client-Staff Assignments
# ---------------------------------------------------------------------------

@router.get("/clients/{client_id}/assignments")
async def list_assignments(
    client_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List staff assigned to a client."""
    # Verify client
    stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Client not found")

    from app.models.user import User as UserModel
    stmt = (
        select(ClientUserLink, UserModel)
        .join(UserModel, UserModel.id == ClientUserLink.user_id)
        .where(ClientUserLink.client_id == client_id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    assignments = [
        ClientAssignmentResponse(
            id=link.id,
            client_id=link.client_id,
            user_id=link.user_id,
            user_name=u.name,
            user_role=u.role,
            relation=link.relation,
        )
        for link, u in rows
    ]
    return {"assignments": assignments}


@router.post("/clients/{client_id}/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(
    client_id: str,
    req: ClientAssignRequest,
    user: User = Depends(require_roles("org_admin", "bcba")),
    db: AsyncSession = Depends(get_db),
):
    """Assign a teacher or parent to a client."""
    # Verify client
    stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify target user exists in same tenant
    from app.models.user import User as UserModel
    stmt = select(UserModel).where(
        UserModel.id == req.user_id,
        UserModel.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Validate relation matches user role
    role_relation_map = {
        UserRole.TEACHER.value: "teacher",
        UserRole.PARENT.value: "parent",
    }
    expected = role_relation_map.get(target_user.role)
    if expected is None:
        raise HTTPException(status_code=400, detail="只能分配老师或家长角色的用户")
    if expected != req.relation:
        raise HTTPException(status_code=400, detail=f"用户角色与分配关系不匹配（用户是{target_user.role}）")

    link = ClientUserLink(
        client_id=client_id,
        user_id=req.user_id,
        relation=req.relation,
    )
    db.add(link)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="该用户已分配到此个案")

    await db.refresh(link)
    return ClientAssignmentResponse(
        id=link.id,
        client_id=link.client_id,
        user_id=link.user_id,
        user_name=target_user.name,
        user_role=target_user.role,
        relation=link.relation,
    )


@router.delete("/clients/{client_id}/assignments/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    client_id: str,
    link_id: str,
    user: User = Depends(require_roles("org_admin", "bcba")),
    db: AsyncSession = Depends(get_db),
):
    """Remove a staff assignment from a client."""
    stmt = select(ClientUserLink).where(
        ClientUserLink.id == link_id,
        ClientUserLink.client_id == client_id,
    )
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="分配记录不存在")

    # Verify client belongs to tenant
    c_stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    c_result = await db.execute(c_stmt)
    if c_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Client not found")

    await db.delete(link)
    await db.commit()


# ---------------------------------------------------------------------------
# Staff listing
# ---------------------------------------------------------------------------

@router.get("/staff")
async def list_staff(
    include_parents: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List assignable users for the current tenant.
    Default: teachers + BCBAs. Pass ?include_parents=true to also include parents
    (needed when assigning parent role in StaffAssignmentPanel).
    """
    roles: list[UserRole] = [UserRole.TEACHER, UserRole.BCBA]
    if include_parents:
        roles.append(UserRole.PARENT)
    stmt = select(User).where(
        User.tenant_id == user.tenant_id,
        User.is_active == True,  # noqa: E712  — SQLAlchemy column compare
        User.role.in_(roles),
    )
    result = await db.execute(stmt)
    staff = result.scalars().all()
    return {"staff": [StaffResponse.model_validate(s) for s in staff]}



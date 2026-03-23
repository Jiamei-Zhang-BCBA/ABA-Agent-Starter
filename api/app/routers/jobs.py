"""Job endpoints: submit, list, detail, output, delivery."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.job import Job, JobStatus, Upload, ParseStatus
from app.models.client import Client
from app.schemas.job import JobCreateRequest, JobResponse, JobDetailResponse, JobListResponse
from app.services.auth_service import get_current_user
from app.services.feature_gate import check_feature_access
from app.services.form_validator import validate_form_data, validate_file_extensions
from app.middleware.rate_limiter import limiter
from app.services.vault_service import create_vault_service
from app.services.file_processor import parse_file

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _dispatch_job(job_id: str) -> None:
    """Dispatch a job for processing: Celery if available and connected, else background thread."""
    try:
        from app.config import get_settings
        _s = get_settings()
        # Only attempt Celery if Redis URL is configured and reachable
        if _s.redis_url and _s.redis_url != "redis://localhost:6379/0":
            from app.workers.job_worker import process_job_task
            if process_job_task is not None:
                process_job_task.delay(job_id)
                return
    except Exception:
        pass  # Celery/Redis not available, fall through

    # Fallback to local background thread
    from app.services.local_worker import process_job_background
    process_job_background(job_id)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
    feature_id: str = Form(...),
    client_id: str | None = Form(None),
    form_data: str = Form("{}"),  # JSON string
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a new job.
    Accepts multipart form: feature_id, client_id, form_data (JSON), files.
    """
    import json

    # Validate feature access
    check_feature_access(user, feature_id)

    # Validate file count and size
    from app.config import get_settings
    _settings = get_settings()

    if len(files) > _settings.max_uploads_per_job:
        raise HTTPException(
            status_code=400,
            detail=f"最多上传 {_settings.max_uploads_per_job} 个文件",
        )

    max_bytes = _settings.max_upload_size_mb * 1024 * 1024
    for f in files:
        content = await f.read()
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"文件 {f.filename} 超过 {_settings.max_upload_size_mb}MB 限制",
            )
        await f.seek(0)  # Reset for later read

    # Validate file extensions
    if files:
        try:
            validate_file_extensions(feature_id, [f.filename for f in files if f.filename])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Parse and validate form_data
    try:
        parsed_form = validate_form_data(feature_id, json.loads(form_data))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid form_data JSON")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate client access for teacher/parent roles
    parsed_client_id = None
    if client_id:
        parsed_client_id = client_id
        await _check_client_access(db, user, parsed_client_id)

    # Create job record
    job = Job(
        tenant_id=user.tenant_id,
        user_id=user.id,
        client_id=parsed_client_id,
        feature_id=feature_id,
        form_data_json=parsed_form,
        status=JobStatus.QUEUED.value,
    )
    db.add(job)
    await db.flush()  # get job.id

    # Handle file uploads
    vault = create_vault_service(str(user.tenant_id))
    upload_ids = []

    for f in files:
        file_bytes = await f.read()
        upload_path = f"{job.id}/{f.filename}"
        vault.upload_raw_file(upload_path, file_bytes, f.content_type or "application/octet-stream")

        upload = Upload(
            job_id=job.id,
            tenant_id=user.tenant_id,
            original_filename=f.filename,
            file_type=f.filename.rsplit(".", 1)[-1] if "." in f.filename else "unknown",
            storage_path=upload_path,
            parse_status=ParseStatus.PENDING.value,
        )
        db.add(upload)
        await db.flush()
        upload_ids.append(str(upload.id))

    job.upload_ids = upload_ids
    db.add(job)

    from app.services.audit_service import log_action
    await log_action(
        db, tenant_id=str(user.tenant_id), user_id=str(user.id),
        action="job.created", resource_type="job", resource_id=str(job.id),
        detail={"feature_id": feature_id, "file_count": len(files)},
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(job)

    # Dispatch async processing
    _dispatch_job(str(job.id))

    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List jobs visible to the current user."""
    conditions = [Job.tenant_id == user.tenant_id]

    # Teachers and parents only see their own jobs
    if user.role in (UserRole.TEACHER, UserRole.PARENT):
        conditions.append(Job.user_id == user.id)

    stmt = (
        select(Job)
        .where(and_(*conditions))
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    jobs = list(result.scalars().all())

    # Count total
    from sqlalchemy import func
    count_stmt = select(func.count(Job.id)).where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar()

    return JobListResponse(jobs=jobs, total=total)


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get job details."""
    job = await _get_job_with_access(db, user, job_id)
    return job


@router.get("/{job_id}/output")
async def get_job_output(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the output content of a completed job."""
    job = await _get_job_with_access(db, user, job_id)

    if job.status not in (JobStatus.DELIVERED.value, JobStatus.APPROVED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not yet delivered. Current status: {job.status}",
        )

    return {
        "job_id": str(job.id),
        "feature_id": job.feature_id,
        "status": job.status,
        "output_content": job.output_content,
    }


class OutputUpdateRequest(BaseModel):
    output_content: str


@router.patch("/{job_id}/output")
async def update_job_output(
    job_id: str,
    body: OutputUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the output content of a delivered job (edit by user)."""
    job = await _get_job_with_access(db, user, job_id)

    if job.status not in (JobStatus.DELIVERED.value, JobStatus.APPROVED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit job in status: {job.status}",
        )

    job.output_content = body.output_content
    db.add(job)
    await db.commit()

    return {"job_id": str(job.id), "status": "updated"}


async def _get_job_with_access(db: AsyncSession, user: User, job_id: str) -> Job:
    """Fetch a job and verify the user has access."""
    stmt = select(Job).where(Job.id == job_id, Job.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Teachers/parents can only see their own jobs
    if user.role in (UserRole.TEACHER, UserRole.PARENT) and job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return job


async def _check_client_access(db: AsyncSession, user: User, client_id: str) -> None:
    """Verify user has access to this client."""
    stmt = select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # For teacher/parent, check link table
    if user.role in (UserRole.TEACHER, UserRole.PARENT):
        from app.models.client import ClientUserLink
        link_stmt = select(ClientUserLink).where(
            ClientUserLink.client_id == client_id,
            ClientUserLink.user_id == user.id,
        )
        link_result = await db.execute(link_stmt)
        if link_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this client")

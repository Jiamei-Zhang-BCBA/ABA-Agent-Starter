"""Review endpoints: list pending, approve, reject, AI-assisted revision."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.review import (
    ReviewResponse, ReviewApproveRequest, ReviewRejectRequest,
    AIReviseRequest, AIReviseResponse,
)
from app.services.auth_service import require_roles
from app.services import review_service

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.get("")
async def list_reviews(
    user: User = Depends(require_roles("org_admin", "bcba")),
    db: AsyncSession = Depends(get_db),
):
    """List pending reviews for the current tenant."""
    reviews = await review_service.get_pending_reviews(db, user.tenant_id)
    return {"reviews": [ReviewResponse.model_validate(r) for r in reviews]}


@router.post("/ai-revise", response_model=AIReviseResponse)
async def ai_revise(
    req: AIReviseRequest,
    user: User = Depends(require_roles("org_admin", "bcba")),
):
    """AI-assisted document revision via Claude CLI."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="文档内容不能为空")
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="修改指令不能为空")
    if len(req.content) > 50_000:
        raise HTTPException(status_code=400, detail="文档内容过长（最大 50000 字符）")
    if len(req.instruction) > 2_000:
        raise HTTPException(status_code=400, detail="修改指令过长（最大 2000 字符）")

    try:
        result = await asyncio.to_thread(
            review_service.ai_revise_content,
            req.content,
            req.instruction,
        )
        return AIReviseResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{review_id}/approve", response_model=ReviewResponse)
async def approve(
    review_id: str,
    req: ReviewApproveRequest,
    user: User = Depends(require_roles("org_admin", "bcba")),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending review, optionally with modifications."""
    try:
        review = await review_service.approve_review(
            db, review_id, user,
            modified_content=req.modified_content,
            comments=req.comments,
        )
        return review
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{review_id}/reject", response_model=ReviewResponse)
async def reject(
    review_id: str,
    req: ReviewRejectRequest,
    user: User = Depends(require_roles("org_admin", "bcba")),
    db: AsyncSession = Depends(get_db),
):
    """Reject a review with comments."""
    try:
        review = await review_service.reject_review(
            db, review_id, user, comments=req.comments,
        )
        return review
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

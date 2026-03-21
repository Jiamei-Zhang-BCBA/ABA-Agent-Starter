"""
ReviewQueueService — manages the expert review workflow.
Jobs with _review_tier="expert" enter the review queue before delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.review import Review, ReviewStatus
from app.models.user import User


async def create_review(db: AsyncSession, job: Job, output_content: str) -> Review:
    """Create a pending review for an expert-tier job."""
    review = Review(
        job_id=job.id,
        output_content=output_content,
        status=ReviewStatus.PENDING.value,
    )
    db.add(review)

    job.status = JobStatus.PENDING_REVIEW.value
    db.add(job)

    await db.commit()
    await db.refresh(review)
    return review


async def get_pending_reviews(
    db: AsyncSession,
    tenant_id: str,
) -> list[Review]:
    """Get all pending reviews for a tenant."""
    stmt = (
        select(Review)
        .join(Job, Review.job_id == Job.id)
        .where(
            and_(
                Job.tenant_id == tenant_id,
                Review.status == ReviewStatus.PENDING.value,
            )
        )
        .order_by(Review.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def approve_review(
    db: AsyncSession,
    review_id: str,
    reviewer: User,
    modified_content: str | None = None,
    comments: str | None = None,
) -> Review:
    """Approve a review, optionally with modifications."""
    stmt = select(Review).where(Review.id == review_id)
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()

    if review is None:
        raise ValueError("Review not found")

    review.reviewer_id = reviewer.id
    review.status = ReviewStatus.APPROVED.value
    review.modified_content = modified_content
    review.comments = comments
    review.reviewed_at = datetime.now(timezone.utc)
    db.add(review)

    # Update job status
    stmt = select(Job).where(Job.id == review.job_id)
    result = await db.execute(stmt)
    job = result.scalar_one()

    final_content = modified_content if modified_content else review.output_content
    job.output_content = final_content
    job.status = JobStatus.DELIVERED.value
    job.completed_at = datetime.now(timezone.utc)
    db.add(job)

    await db.commit()
    await db.refresh(review)
    return review


async def reject_review(
    db: AsyncSession,
    review_id: str,
    reviewer: User,
    comments: str,
) -> Review:
    """Reject a review with comments."""
    stmt = select(Review).where(Review.id == review_id)
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()

    if review is None:
        raise ValueError("Review not found")

    review.reviewer_id = reviewer.id
    review.status = ReviewStatus.REJECTED.value
    review.comments = comments
    review.reviewed_at = datetime.now(timezone.utc)
    db.add(review)

    # Update job status
    stmt = select(Job).where(Job.id == review.job_id)
    result = await db.execute(stmt)
    job = result.scalar_one()
    job.status = JobStatus.REJECTED.value
    db.add(job)

    await db.commit()
    await db.refresh(review)
    return review

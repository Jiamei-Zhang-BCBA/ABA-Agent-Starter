"""
ReviewQueueService — manages the expert review workflow.
Jobs with _review_tier="expert" enter the review queue before delivery.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.client import Client, ClientStatus
from app.models.job import Job, JobStatus
from app.models.review import Review, ReviewStatus
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()


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

    # Auto-create Client record for intake jobs
    if job.feature_id == "intake" and job.form_data_json:
        alias = job.form_data_json.get("child_alias", "")
        if alias:
            code_name = f"A-{alias}"
            # Check if client already exists
            existing = await db.execute(
                select(Client).where(
                    Client.tenant_id == job.tenant_id,
                    Client.code_name == code_name,
                )
            )
            if existing.scalar_one_or_none() is None:
                client = Client(
                    tenant_id=job.tenant_id,
                    code_name=code_name,
                    display_alias=alias,
                    status=ClientStatus.ACTIVE.value,
                )
                db.add(client)
                job.client_id = client.id
                logger.info("Auto-created client %s for intake job %s", code_name, job.id)

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


def ai_revise_content(content: str, instruction: str) -> dict:
    """
    Call Claude CLI to revise a document according to an instruction.
    Synchronous — the router wraps this with asyncio.to_thread().
    """
    system_prompt = (
        "你是一位专业的 ABA 临床文档修改助手。用户会给你一份已有的文档和一条修改指令。\n"
        "请严格按照修改指令对文档进行修改，保留文档的整体结构和未涉及的内容。\n"
        "只输出修改后的完整文档，不要添加任何解释、前言或后记。\n"
        "保持原文的 Markdown 格式。"
    )

    user_message = (
        f"## 原始文档\n\n{content}\n\n"
        f"---\n\n"
        f"## 修改指令\n\n{instruction}"
    )

    combined_prompt = (
        f"<system-instructions>\n{system_prompt}\n</system-instructions>\n\n"
        f"---\n\n{user_message}"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(combined_prompt)
        prompt_path = tmp.name

    try:
        cmd = [
            settings.claude_cli_path,
            "-p",
            "--model", "sonnet",
            "--output-format", "json",
            "--no-session-persistence",
        ]

        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()

        proc = subprocess.run(
            cmd,
            input=prompt_text,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
        )

        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown CLI error"
            logger.error("[AI Revise] claude failed (rc=%d): %s", proc.returncode, error_msg)
            raise RuntimeError(f"Claude CLI 调用失败: {error_msg}")

        try:
            output_data = json.loads(proc.stdout)
            revised = output_data.get("result", "")
            input_tokens = output_data.get("input_tokens", 0)
            output_tokens = output_data.get("output_tokens", 0)
        except (json.JSONDecodeError, KeyError):
            revised = proc.stdout.strip()
            input_tokens = 0
            output_tokens = 0

        return {
            "revised_content": revised,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
    finally:
        Path(prompt_path).unlink(missing_ok=True)

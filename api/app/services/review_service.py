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

                # Initialize vault directories for the new client
                try:
                    from app.services.vault_service import create_vault_service, init_client_vault
                    vault = create_vault_service(str(job.tenant_id))
                    init_client_vault(vault, code_name)
                    logger.info("Initialized vault for client %s", code_name)
                except Exception:
                    logger.exception("Failed to initialize vault for client %s", code_name)

    # Write approved output to vault
    try:
        from app.services.vault_service import create_vault_service, write_output_to_vault
        from app.core.feature_registry import get_feature
        vault = create_vault_service(str(job.tenant_id))
        feature = get_feature(job.feature_id)
        if feature:
            # Determine client_code: prefer form_data (always available), fallback to DB
            client_code = ""
            if job.form_data_json:
                alias = job.form_data_json.get("child_alias", "")
                if alias:
                    client_code = f"A-{alias}"
            if not client_code and job.client_id:
                client_result = await db.execute(
                    select(Client).where(Client.id == job.client_id)
                )
                client_obj = client_result.scalar_one_or_none()
                if client_obj:
                    client_code = client_obj.code_name
            if client_code:
                write_output_to_vault(vault, feature._skill_name, client_code, final_content)
                logger.info("Wrote approved output to vault for job %s (client: %s)", job.id, client_code)
            else:
                logger.warning("No client_code for job %s, skipping vault write", job.id)
    except Exception:
        logger.exception("Failed to write approved output to vault for job %s", job.id)

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


def _build_structure_guard(vault_path: str | None) -> str:
    """Build structure protection rules based on the vault file path."""
    if not vault_path:
        return ""

    rules: list[str] = []

    if "核心档案" in vault_path:
        rules.append(
            "此文件是核心档案，以下章节标题是系统锚点，绝对不能删除、重命名或移动：\n"
            "- 基本背景\n"
            "- 核心能力画像\n"
            "- 强化物偏好清单\n"
            "- 历史问题行为备忘 / 问题行为预警\n"
            "- 当前目标摘要\n"
            "- 全生命周期索引\n"
            "- 变更日志\n"
            "你只能修改章节内的内容，不能改变章节标题文字（忽略 emoji 差异）。\n"
            "frontmatter（--- 之间的 YAML 头）中的 tags 和 child_alias 字段不能删除。"
        )
    elif "IEP" in vault_path:
        rules.append(
            "此文件是 IEP（个别化教育计划），保留所有目标编号和层级结构。\n"
            "不要删除或合并已有的目标条目，只修改指令涉及的部分。"
        )
    elif "FBA" in vault_path or "功能行为分析" in vault_path:
        rules.append(
            "此文件是 FBA（功能行为分析），保留 ABC 记录格式和功能假说结构。\n"
            "不要改变行为定义的操作性描述格式。"
        )
    elif "初访信息表" in vault_path:
        rules.append(
            "此文件是初访信息表，保留所有表格结构和字段名。\n"
            "只修改字段值，不要改变表格列名或整体结构。"
        )
    elif "成长档案" in vault_path:
        rules.append(
            "此文件是教师成长档案，保留时间线条目的日期格式和层级结构。\n"
            "新内容追加到末尾，不要删除历史记录。"
        )
    elif "日志" in vault_path or "Sessions" in vault_path:
        rules.append(
            "此文件是课后记录/日志，保留日期、教师、个案等元数据字段。\n"
            "不要改变记录的时间戳和基本结构。"
        )

    if not rules:
        return ""

    return "\n\n【结构保护规则】\n" + "\n".join(rules)


def ai_revise_content(content: str, instruction: str, vault_path: str | None = None) -> dict:
    """
    Call Claude CLI to revise a document according to an instruction.
    Synchronous — the router wraps this with asyncio.to_thread().
    """
    structure_guard = _build_structure_guard(vault_path)

    system_prompt = (
        "你是一位专业的 ABA 临床文档修改助手。用户会给你一份已有的文档和一条修改指令。\n"
        "请严格按照修改指令对文档进行修改，保留文档的整体结构和未涉及的内容。\n"
        "只输出修改后的完整文档，不要添加任何解释、前言或后记。\n"
        "保持原文的 Markdown 格式。"
        f"{structure_guard}"
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

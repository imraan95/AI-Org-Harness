from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import JobRow


async def enqueue_job(
    session: AsyncSession, type: str, payload: dict[str, Any]
) -> uuid.UUID:
    row = JobRow(type=type, payload=payload)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row.id


async def dequeue_job(session: AsyncSession) -> JobRow | None:
    """Claim and return the oldest pending job, or None if there isn't one.

    Uses SELECT ... FOR UPDATE SKIP LOCKED so concurrent workers never claim
    the same job twice.
    """
    result = await session.execute(
        select(JobRow)
        .where(JobRow.status == "pending")
        .order_by(JobRow.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    row.status = "claimed"
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return row


async def mark_job_done(session: AsyncSession, job_id: uuid.UUID) -> None:
    await session.execute(
        update(JobRow)
        .where(JobRow.id == job_id)
        .values(status="done", updated_at=datetime.now(timezone.utc))
    )
    await session.commit()

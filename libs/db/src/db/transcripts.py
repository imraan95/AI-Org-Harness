from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_schemas import Transcript

from .models import TranscriptRow


async def insert_transcript(session: AsyncSession, transcript: Transcript) -> None:
    row = TranscriptRow(
        id=transcript.id,
        meeting_title=transcript.meeting_title,
        attendees=transcript.attendees,
        meeting_date=transcript.meeting_date,
        source=transcript.source,
        raw_text=transcript.raw_text,
    )
    session.add(row)
    await session.commit()


async def get_transcript(session: AsyncSession, transcript_id: str) -> Transcript | None:
    result = await session.execute(
        select(TranscriptRow).where(TranscriptRow.id == transcript_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    return Transcript(
        id=row.id,
        meeting_title=row.meeting_title,
        attendees=row.attendees,
        meeting_date=row.meeting_date,
        source=row.source,
        raw_text=row.raw_text,
    )

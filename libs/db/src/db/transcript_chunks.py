from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_schemas import TranscriptChunk

from .models import TranscriptChunkRow


async def insert_transcript_chunks(
    session: AsyncSession, transcript_id: str, chunks: list[TranscriptChunk]
) -> None:
    for chunk in chunks:
        row = TranscriptChunkRow(
            id=chunk.id,
            transcript_id=transcript_id,
            text=chunk.text,
            embedding=chunk.embedding,
            order=chunk.order,
        )
        session.add(row)
    await session.commit()


async def get_chunks_by_transcript_id(
    session: AsyncSession, transcript_id: str
) -> list[TranscriptChunk]:
    result = await session.execute(
        select(TranscriptChunkRow)
        .where(TranscriptChunkRow.transcript_id == transcript_id)
        .order_by(TranscriptChunkRow.order)
    )
    rows = result.scalars().all()

    return [
        TranscriptChunk(
            id=row.id,
            transcript_id=row.transcript_id,
            text=row.text,
            embedding=list(row.embedding) if row.embedding is not None else [],
            order=row.order,
        )
        for row in rows
    ]

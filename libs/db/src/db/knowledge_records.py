from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType

from .models import KnowledgeRecordRow


def _row_to_record(row: KnowledgeRecordRow) -> KnowledgeRecord:
    return KnowledgeRecord(
        id=row.id,
        type=row.type,
        topic=row.topic,
        statement=row.statement,
        status=row.status,
        confidence=row.confidence,
        source_ids=list(row.source_ids),
        people=list(row.people),
        created_at=row.created_at,
        observed_at=row.observed_at,
        last_updated_at=row.last_updated_at,
        supersedes=row.supersedes,
        superseded_at=row.superseded_at,
        conflicts_with=list(row.conflicts_with),
        workspace_id=row.workspace_id,
        source_id=row.source_id,
        visibility=row.visibility,
        owner=row.owner,
        access_level=row.access_level,
        edited_by=row.edited_by,
    )


def _record_to_row(record: KnowledgeRecord) -> KnowledgeRecordRow:
    return KnowledgeRecordRow(
        id=record.id,
        type=record.type,
        topic=record.topic,
        statement=record.statement,
        status=record.status.value,
        confidence=record.confidence,
        source_ids=list(record.source_ids),
        people=list(record.people),
        created_at=record.created_at,
        observed_at=record.observed_at,
        last_updated_at=record.last_updated_at,
        supersedes=record.supersedes,
        superseded_at=record.superseded_at,
        conflicts_with=list(record.conflicts_with),
        workspace_id=record.workspace_id,
        source_id=record.source_id,
        visibility=record.visibility,
        owner=record.owner,
        access_level=record.access_level,
        edited_by=record.edited_by,
    )


async def upsert_knowledge_record(session: AsyncSession, record: KnowledgeRecord) -> None:
    """Insert `record`, or replace it in place if its id already exists -
    same create-or-replace semantics as `RealOpenVikingClient.write_knowledge`
    (SQLAlchemy's `merge()` is exactly INSERT-or-UPDATE-by-primary-key)."""
    await session.merge(_record_to_row(record))
    await session.commit()


async def get_knowledge_record_by_id(
    session: AsyncSession, knowledge_id: str
) -> KnowledgeRecord | None:
    row = await session.get(KnowledgeRecordRow, knowledge_id)
    return _row_to_record(row) if row is not None else None


async def get_knowledge_records_by_topic(
    session: AsyncSession, topic: str
) -> list[KnowledgeRecord]:
    """Exact topic-string match - same deliberate semantics as
    `RealOpenVikingClient.get_relevant_knowledge` (docs/decisions/0007,
    0008): topic-name drift is bridged one layer up, via `match_topic`."""
    result = await session.execute(
        select(KnowledgeRecordRow).where(KnowledgeRecordRow.topic == topic)
    )
    return [_row_to_record(row) for row in result.scalars()]


async def list_conflicting_knowledge_records(
    session: AsyncSession,
) -> list[KnowledgeRecord]:
    result = await session.execute(
        select(KnowledgeRecordRow).where(
            KnowledgeRecordRow.status == KnowledgeStatus.CONFLICTING.value
        )
    )
    return [_row_to_record(row) for row in result.scalars()]


async def list_knowledge_records_by_type(
    session: AsyncSession, knowledge_type: KnowledgeType
) -> list[KnowledgeRecord]:
    result = await session.execute(
        select(KnowledgeRecordRow).where(KnowledgeRecordRow.type == knowledge_type.value)
    )
    return [_row_to_record(row) for row in result.scalars()]


async def list_all_knowledge_records(session: AsyncSession) -> list[KnowledgeRecord]:
    """No 256-match cap here (unlike OpenViking's glob-based `list_all`) -
    a plain, unpaginated `SELECT *`. Fine at this data's current scale;
    add real pagination if that ever changes."""
    result = await session.execute(select(KnowledgeRecordRow))
    return [_row_to_record(row) for row in result.scalars()]


async def update_knowledge_record_status(
    session: AsyncSession, knowledge_id: str, status: KnowledgeStatus
) -> None:
    await session.execute(
        update(KnowledgeRecordRow)
        .where(KnowledgeRecordRow.id == knowledge_id)
        .values(status=status.value)
    )
    await session.commit()


async def update_knowledge_record_fields(
    session: AsyncSession, knowledge_id: str, updates: dict, edited_by: str
) -> None:
    await session.execute(
        update(KnowledgeRecordRow)
        .where(KnowledgeRecordRow.id == knowledge_id)
        .values(**updates, edited_by=edited_by)
    )
    await session.commit()


async def mark_knowledge_record_superseded(
    session: AsyncSession, knowledge_id: str, superseded_at
) -> None:
    await session.execute(
        update(KnowledgeRecordRow)
        .where(KnowledgeRecordRow.id == knowledge_id)
        .values(status=KnowledgeStatus.SUPERSEDED.value, superseded_at=superseded_at)
    )
    await session.commit()


async def delete_knowledge_record(session: AsyncSession, knowledge_id: str) -> None:
    """Not part of `OpenVikingClient`'s interface - test cleanup only."""
    await session.execute(
        delete(KnowledgeRecordRow).where(KnowledgeRecordRow.id == knowledge_id)
    )
    await session.commit()

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CustomKnowledgeTypeRow


async def list_custom_knowledge_types(
    session: AsyncSession, workspace_id: str = "default"
) -> list[CustomKnowledgeTypeRow]:
    result = await session.execute(
        select(CustomKnowledgeTypeRow)
        .where(CustomKnowledgeTypeRow.workspace_id == workspace_id)
        .order_by(CustomKnowledgeTypeRow.created_at)
    )
    return list(result.scalars())


async def create_custom_knowledge_type(
    session: AsyncSession, workspace_id: str, key: str, label: str
) -> CustomKnowledgeTypeRow | None:
    """Add a custom type. Returns None if `key` is already taken in this
    workspace (the migration's `unique (workspace_id, key)` constraint),
    rather than raising - the caller (harness-api) turns that into a 409.
    """
    row = CustomKnowledgeTypeRow(workspace_id=workspace_id, key=key, label=label)
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return None
    await session.refresh(row)
    return row


async def delete_custom_knowledge_type(
    session: AsyncSession, workspace_id: str, key: str
) -> bool:
    """Returns True if a row was deleted, False if none matched."""
    result = await session.execute(
        delete(CustomKnowledgeTypeRow).where(
            CustomKnowledgeTypeRow.workspace_id == workspace_id,
            CustomKnowledgeTypeRow.key == key,
        )
    )
    await session.commit()
    return result.rowcount > 0

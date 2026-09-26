from __future__ import annotations

from datetime import datetime

from db import (
    get_knowledge_record_by_id,
    get_knowledge_records_by_topic,
    get_session_factory,
    list_all_knowledge_records,
    list_conflicting_knowledge_records,
    list_knowledge_records_by_type,
    mark_knowledge_record_superseded,
    update_knowledge_record_fields,
    update_knowledge_record_status,
    upsert_knowledge_record,
)
from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType

from .interface import OpenVikingClient


class PostgresOpenVikingClient(OpenVikingClient):
    """Stores knowledge records in our own Postgres (Supabase), instead of
    OpenViking's file store.

    Why this exists: since docs/decisions/0008 moved topic-drift bridging
    off OpenViking's semantic search entirely, all OpenViking was actually
    doing for us was plain file storage plus `glob`/`grep` pattern
    matching - "a smart-ish filesystem" per that decision's own wording.
    A plain table does the exact same job, without the 256-match glob cap
    (build-plan.md's own confirmed-real issue), without keeping an AGPL
    fork running as a network service, and without one more Docker
    container's worth of resources on a production box.

    OpenViking's own client/tests are untouched and still pass - this is a
    second `OpenVikingClient` implementation, not a replacement of the
    first. Whichever one is actually used at runtime is decided by a small
    factory (see harness_api/context_agent's own construction points), not
    by anything in this class.

    A fresh `AsyncSession` is opened per call (via a shared session
    factory) rather than one held open across calls - matches this
    codebase's existing "SQLAlchemy sessions are event-loop-bound, don't
    share one across requests" rule (see e.g. ingestion-service's own
    per-request client comment).
    """

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or get_session_factory()

    async def write_knowledge(self, record: KnowledgeRecord) -> None:
        async with self._session_factory() as session:
            await upsert_knowledge_record(session, record)

    async def get_knowledge_by_id(self, knowledge_id: str) -> KnowledgeRecord | None:
        async with self._session_factory() as session:
            return await get_knowledge_record_by_id(session, knowledge_id)

    async def get_relevant_knowledge(self, topic: str) -> list[KnowledgeRecord]:
        async with self._session_factory() as session:
            return await get_knowledge_records_by_topic(session, topic)

    async def list_conflicts(self) -> list[KnowledgeRecord]:
        async with self._session_factory() as session:
            return await list_conflicting_knowledge_records(session)

    async def list_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeRecord]:
        async with self._session_factory() as session:
            return await list_knowledge_records_by_type(session, knowledge_type)

    async def list_all(self) -> list[KnowledgeRecord]:
        async with self._session_factory() as session:
            return await list_all_knowledge_records(session)

    async def update_knowledge_status(
        self, knowledge_id: str, status: KnowledgeStatus
    ) -> None:
        async with self._session_factory() as session:
            await update_knowledge_record_status(session, knowledge_id, status)

    async def update_knowledge_fields(
        self, knowledge_id: str, updates: dict, edited_by: str
    ) -> None:
        async with self._session_factory() as session:
            await update_knowledge_record_fields(session, knowledge_id, updates, edited_by)

    async def mark_superseded(self, knowledge_id: str, superseded_at: datetime) -> None:
        async with self._session_factory() as session:
            await mark_knowledge_record_superseded(session, knowledge_id, superseded_at)

    async def aclose(self) -> None:
        # Not part of `OpenVikingClient`'s abstract interface, but
        # `RealOpenVikingClient` has one and some call sites (e.g.
        # harness-api's `get_openviking_client` dependency) call it
        # unconditionally in a `finally` block - a no-op here since there's
        # no persistent connection held open between calls to close.
        pass

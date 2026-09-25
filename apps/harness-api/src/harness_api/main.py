"""T050: harness-api scaffold - GET /knowledge/{id}.
T051: protected by a logged-in user's Supabase Auth token.
T052: also accepts a static service key, for non-user callers.
T053: GET /decisions, /people, /conflicts - filtered list views.
T054: GET /context, /context/product, /context/customer, /context/strategy.
T055: POST /knowledge/{id}/approve.
T056: POST /knowledge/{id}/reject.
T057: POST /knowledge/{id}/edit.
T058: GET /knowledge/{id} includes a `sources` array (meeting title/date).
T059: GET /knowledge/{id}/history - walk the supersedes chain.
T061: GET /health - unauthenticated liveness check, so other services
(apps/mcp-server's tests) can detect a real running instance.
T077: GET/POST /taxonomy/types, DELETE /taxonomy/types/{key} - a workspace's
custom knowledge types on top of the fixed `KnowledgeType` built-ins; POST
/knowledge/{id}/edit also accepts a `type`, validated against built-in ∪
custom here (KnowledgeRecord.type itself is now a plain str - see
knowledge_model's models.py comment).
"""

from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator

from db import (
    create_custom_knowledge_type,
    delete_custom_knowledge_type,
    get_session_factory,
    get_transcript,
    list_custom_knowledge_types,
)
from fastapi import Depends, FastAPI, HTTPException
from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType
from openviking_client import OpenVikingClient, RealOpenVikingClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import get_current_user_or_service

app = FastAPI(title="harness-api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


class Source(BaseModel):
    """One piece of provenance for a knowledge record - PRD's "show the
    meetings supporting each memory" (§16.C), not the raw transcript id.
    """

    meeting_title: str
    meeting_date: datetime


class KnowledgeRecordWithSources(KnowledgeRecord):
    sources: list[Source] = []


class KnowledgeEditRequest(BaseModel):
    """Fields a human reviewer can edit before a proposed record goes
    active (PRD §17/§20). Only the fields a human plausibly corrects by
    hand for MVP - not every KnowledgeRecord field is open to editing here
    (e.g. status has its own approve/reject routes, ids/timestamps aren't
    editable at all).
    """

    edited_by: str
    statement: str | None = None
    topic: str | None = None
    confidence: float | None = None
    type: str | None = None


class TaxonomyType(BaseModel):
    """One entry in a workspace's knowledge taxonomy - either one of the
    fixed `KnowledgeType` built-ins, or a custom type someone added."""

    key: str
    label: str
    builtin: bool


class TaxonomyTypeCreateRequest(BaseModel):
    key: str
    label: str


def _builtin_taxonomy_types() -> list[TaxonomyType]:
    return [
        TaxonomyType(key=t.value, label=t.value.replace("_", " ").title(), builtin=True)
        for t in KnowledgeType
    ]


async def _all_taxonomy_types(
    session: AsyncSession, workspace_id: str = "default"
) -> list[TaxonomyType]:
    custom = await list_custom_knowledge_types(session, workspace_id)
    return _builtin_taxonomy_types() + [
        TaxonomyType(key=row.key, label=row.label, builtin=False) for row in custom
    ]


async def get_openviking_client() -> AsyncIterator[OpenVikingClient]:
    # Created fresh per request, not once at module scope - an
    # httpx.AsyncClient binds to whichever event loop first uses it, and a
    # shared instance breaks under pytest's per-test event loops (see the
    # same fix in ingestion-service's main.py, T047).
    client = RealOpenVikingClient()
    try:
        yield client
    finally:
        await client.aclose()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    # Same fresh-per-request reasoning as get_openviking_client - a
    # SQLAlchemy async engine is event-loop-bound too.
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


@app.get("/knowledge/{knowledge_id}", response_model=KnowledgeRecordWithSources)
async def get_knowledge(
    knowledge_id: str,
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeRecordWithSources:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")

    sources = []
    for source_id in record.source_ids:
        transcript = await get_transcript(session, source_id)
        if transcript is not None:
            sources.append(
                Source(
                    meeting_title=transcript.meeting_title,
                    meeting_date=transcript.meeting_date,
                )
            )
    return KnowledgeRecordWithSources(**record.model_dump(), sources=sources)


@app.get("/knowledge/{knowledge_id}/history", response_model=list[KnowledgeRecord])
async def get_knowledge_history(
    knowledge_id: str,
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")

    # Newest-to-oldest, following `supersedes` backward. `visited` guards
    # against an (invalid, shouldn't-happen) cycle in the data turning this
    # into an infinite loop.
    history = [record]
    visited = {record.id}
    current = record
    while current.supersedes and current.supersedes not in visited:
        previous = await openviking.get_knowledge_by_id(current.supersedes)
        if previous is None:
            break
        history.append(previous)
        visited.add(previous.id)
        current = previous
    return history


@app.get("/decisions", response_model=list[KnowledgeRecord])
async def get_decisions(
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    return await openviking.list_by_type(KnowledgeType.DECISION)


@app.get("/people", response_model=list[KnowledgeRecord])
async def get_people(
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    return await openviking.list_by_type(KnowledgeType.PERSON)


@app.get("/conflicts", response_model=list[KnowledgeRecord])
async def get_conflicts(
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    # PRD §16's "Conflicts" pane is "potential contradictions / pending
    # confirmation" - status-based (KnowledgeStatus.CONFLICTING), not the
    # separate KnowledgeType.CONFLICT enum value. Reuses the method built
    # in T037 for exactly this notion of "conflict", rather than a new
    # type-filtered list.
    return await openviking.list_conflicts()


@app.get("/context", response_model=list[KnowledgeRecord])
async def get_context(
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    return await openviking.list_all()


@app.get("/context/product", response_model=list[KnowledgeRecord])
async def get_context_product(
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    return await openviking.list_by_type(KnowledgeType.PRODUCT_REQUIREMENT)


@app.get("/context/customer", response_model=list[KnowledgeRecord])
async def get_context_customer(
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    return await openviking.list_by_type(KnowledgeType.CUSTOMER_INSIGHT)


@app.get("/context/strategy", response_model=list[KnowledgeRecord])
async def get_context_strategy(
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> list[KnowledgeRecord]:
    return await openviking.list_by_type(KnowledgeType.STRATEGY)


@app.post("/knowledge/{knowledge_id}/approve", response_model=KnowledgeRecord)
async def approve_knowledge(
    knowledge_id: str,
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> KnowledgeRecord:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")
    await openviking.update_knowledge_status(knowledge_id, KnowledgeStatus.ACTIVE)
    return await openviking.get_knowledge_by_id(knowledge_id)


@app.post("/knowledge/{knowledge_id}/reject", response_model=KnowledgeRecord)
async def reject_knowledge(
    knowledge_id: str,
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> KnowledgeRecord:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")
    await openviking.update_knowledge_status(knowledge_id, KnowledgeStatus.REJECTED)
    return await openviking.get_knowledge_by_id(knowledge_id)


@app.post("/knowledge/{knowledge_id}/edit", response_model=KnowledgeRecord)
async def edit_knowledge(
    knowledge_id: str,
    edit: KnowledgeEditRequest,
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeRecord:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")
    if edit.type is not None:
        valid_keys = {t.key for t in await _all_taxonomy_types(session)}
        if edit.type not in valid_keys:
            raise HTTPException(
                status_code=400,
                detail=f"unknown knowledge type {edit.type!r} - not a built-in or custom type",
            )
    updates = edit.model_dump(exclude={"edited_by"}, exclude_none=True)
    await openviking.update_knowledge_fields(knowledge_id, updates, edit.edited_by)
    return await openviking.get_knowledge_by_id(knowledge_id)


@app.get("/taxonomy/types", response_model=list[TaxonomyType])
async def get_taxonomy_types(
    _user: dict = Depends(get_current_user_or_service),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaxonomyType]:
    return await _all_taxonomy_types(session)


@app.post("/taxonomy/types", response_model=TaxonomyType, status_code=201)
async def create_taxonomy_type(
    body: TaxonomyTypeCreateRequest,
    _user: dict = Depends(get_current_user_or_service),
    session: AsyncSession = Depends(get_db_session),
) -> TaxonomyType:
    if body.key in {t.value for t in KnowledgeType}:
        raise HTTPException(
            status_code=409, detail=f"{body.key!r} is already a built-in type"
        )
    row = await create_custom_knowledge_type(session, "default", body.key, body.label)
    if row is None:
        raise HTTPException(
            status_code=409, detail=f"a custom type with key {body.key!r} already exists"
        )
    return TaxonomyType(key=row.key, label=row.label, builtin=False)


@app.delete("/taxonomy/types/{key}", status_code=204)
async def delete_taxonomy_type(
    key: str,
    _user: dict = Depends(get_current_user_or_service),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    if key in {t.value for t in KnowledgeType}:
        raise HTTPException(
            status_code=400, detail="built-in types can't be deleted"
        )
    deleted = await delete_custom_knowledge_type(session, "default", key)
    if not deleted:
        raise HTTPException(status_code=404, detail="custom type not found")

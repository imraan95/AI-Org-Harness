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
"""

from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator

from db import get_session_factory, get_transcript
from fastapi import Depends, FastAPI, HTTPException
from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType
from openviking_client import OpenVikingClient, RealOpenVikingClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import get_current_user_or_service

app = FastAPI(title="harness-api")


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
) -> KnowledgeRecord:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")
    updates = edit.model_dump(exclude={"edited_by"}, exclude_none=True)
    await openviking.update_knowledge_fields(knowledge_id, updates, edit.edited_by)
    return await openviking.get_knowledge_by_id(knowledge_id)

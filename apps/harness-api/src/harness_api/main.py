"""T050: harness-api scaffold - GET /knowledge/{id}.
T051: protected by a logged-in user's Supabase Auth token.
T052: also accepts a static service key, for non-user callers.
T053: GET /decisions, /people, /conflicts - filtered list views.
T054: GET /context, /context/product, /context/customer, /context/strategy.
"""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from knowledge_model import KnowledgeRecord, KnowledgeType
from openviking_client import OpenVikingClient, RealOpenVikingClient

from .auth import get_current_user_or_service

app = FastAPI(title="harness-api")


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


@app.get("/knowledge/{knowledge_id}", response_model=KnowledgeRecord)
async def get_knowledge(
    knowledge_id: str,
    _user: dict = Depends(get_current_user_or_service),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> KnowledgeRecord:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")
    return record


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

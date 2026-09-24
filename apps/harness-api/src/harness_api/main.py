"""T050: harness-api scaffold - GET /knowledge/{id}.
T051: protected by a logged-in user's Supabase Auth token.
"""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from knowledge_model import KnowledgeRecord
from openviking_client import OpenVikingClient, RealOpenVikingClient

from .auth import get_current_user

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
    _user: dict = Depends(get_current_user),
    openviking: OpenVikingClient = Depends(get_openviking_client),
) -> KnowledgeRecord:
    record = await openviking.get_knowledge_by_id(knowledge_id)
    if record is None:
        raise HTTPException(status_code=404, detail="knowledge record not found")
    return record

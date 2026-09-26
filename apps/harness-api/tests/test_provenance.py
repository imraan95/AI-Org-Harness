"""T058: GET /knowledge/{id} includes a `sources` array (meeting
title/date), joined back to `transcripts` via `libs/db`. Knowledge
records are seeded through whichever knowledge store harness-api is
actually configured to use (get_knowledge_store() - Postgres by default,
see openviking_client's router.py).

Needs a real Postgres (for the transcript join, and by default for the
knowledge record too) - skips itself unless reachable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from db import get_session_factory, insert_transcript
from fastapi.testclient import TestClient
from knowledge_model import KnowledgeRecord
from openviking_client import get_knowledge_store
from shared_schemas import Transcript
from sqlalchemy.exc import SQLAlchemyError

from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app


def _db_is_up() -> bool:
    import asyncio

    async def _check() -> bool:
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    try:
        return asyncio.run(_check())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_is_up(),
    reason="Needs a reachable Postgres (`supabase start`).",
)

_AUTH_HEADERS = {"x-service-key": HARNESS_API_SERVICE_KEY}


async def test_get_knowledge_by_id_includes_sources_for_its_transcript():
    transcript_id = f"t058-{uuid.uuid4()}"
    meeting_date = datetime.now(timezone.utc)
    transcript = Transcript(
        id=transcript_id,
        meeting_title="T058 fixture meeting",
        attendees=["Alice"],
        meeting_date=meeting_date,
        source="test",
        raw_text="...",
    )
    session_factory = get_session_factory()
    async with session_factory() as session:
        await insert_transcript(session, transcript)

    record = KnowledgeRecord(
        id=f"K-t058-{uuid.uuid4()}",
        type="fact",
        topic=f"t058_{uuid.uuid4().hex[:8]}",
        statement="Fixture statement for T058's provenance test.",
        status="active",
        confidence=0.75,
        source_ids=[transcript_id],
        people=["Alice"],
        created_at=meeting_date,
        observed_at=meeting_date,
        last_updated_at=meeting_date,
    )
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    client = TestClient(app)
    response = client.get(f"/knowledge/{record.id}", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["meeting_title"] == "T058 fixture meeting"
    # Same "approx, not exact" comparison as libs/db/tests/test_transcripts.py -
    # Postgres timestamp precision doesn't always match Python's exactly.
    returned_date = datetime.fromisoformat(source["meeting_date"])
    assert returned_date.timestamp() == pytest.approx(meeting_date.timestamp())


async def test_get_knowledge_by_id_returns_empty_sources_for_unknown_source_id():
    record = KnowledgeRecord(
        id=f"K-t058-nosrc-{uuid.uuid4()}",
        type="fact",
        topic=f"t058_nosrc_{uuid.uuid4().hex[:8]}",
        statement="Fixture with a source_id that has no matching transcript row.",
        status="active",
        confidence=0.75,
        source_ids=["no-such-transcript"],
        people=[],
        created_at=datetime.now(timezone.utc),
        observed_at=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc),
    )
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    client = TestClient(app)
    response = client.get(f"/knowledge/{record.id}", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["sources"] == []

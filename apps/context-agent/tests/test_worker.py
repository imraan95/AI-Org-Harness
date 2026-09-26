"""T048: the worker loop, including the real end-to-end slice the task
asks for - POST a webhook to ingestion-service, run the worker once,
confirm a knowledge record exists in the real knowledge store
(get_knowledge_store() - Postgres, per docs/decisions/0011).

No skip-guard needed: matches every other Postgres-backed test in this
codebase (e.g. libs/db's own tests). Previously this constructed a real
OpenViking client directly and skipped unless a running OpenViking + API
key were configured - removed along with OpenViking itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

from db import dequeue_job, get_engine, get_session_factory, mark_job_done
from fastapi.testclient import TestClient
from llm_router import FakeLLM
from openviking_client import FakeOpenVikingClient, get_knowledge_store

from context_agent import run_worker_once
from ingestion_service.main import ANARLOG_WEBHOOK_SECRET, app


def _signed_post(client: TestClient, payload: dict):
    body = json.dumps(payload).encode()
    signature = (
        "sha256="
        + hmac.new(ANARLOG_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    )
    return client.post(
        "/webhooks/anarlog",
        content=body,
        headers={
            "content-type": "application/json",
            "x-anarlog-signature": signature,
        },
    )


def _note_enhanced_payload(meeting_id: str, topic_hint: str) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "event": "note.enhanced",
        "created_at": "2026-09-24T06:45:53.265Z",
        "data": {
            "meeting": {
                "id": meeting_id,
                "title": "T048 worker test meeting",
                "note": {"body": "..."},
                "summaries": ["..."],
                "participants": ["Alice"],
                "action_items": [],
            },
            "transcript_text": f"Alice: Testing the worker for {topic_hint}.",
        },
    }


async def test_run_worker_once_returns_none_when_queue_is_empty():
    engine = get_engine()
    session_factory = get_session_factory(engine)

    # There's no "peek without claiming" helper, so drain whatever's
    # already pending first (marking each done, not just claimed, so this
    # doesn't leave its own mess for other tests - see T047's job-queue
    # pollution note in build-plan.md), then confirm the next call - on a
    # queue that's now actually empty - returns None rather than raising.
    async with session_factory() as session:
        while True:
            job = await dequeue_job(session)
            if job is None:
                break
            await mark_job_done(session, job.id)

    async with session_factory() as session:
        result = await run_worker_once(session, FakeLLM(), FakeOpenVikingClient())

    await engine.dispose()
    assert result is None


async def test_worker_processes_a_webhook_ingested_transcript_into_the_knowledge_store():
    run_id = uuid.uuid4().hex[:8]
    topic_hint = f"worker_e2e_{run_id}"
    meeting_id = f"test-meeting-{uuid.uuid4()}"

    client = TestClient(app)
    response = _signed_post(client, _note_enhanced_payload(meeting_id, topic_hint))
    assert response.status_code == 200

    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result(
        [{"topic": topic_hint, "statement": f"Statement about {topic_hint}."}]
    )
    fake_llm.set_next_classify_result("fact")
    knowledge_store = get_knowledge_store()

    engine = get_engine()
    session_factory = get_session_factory(engine)
    try:
        async with session_factory() as session:
            written = await run_worker_once(session, fake_llm, knowledge_store)

        assert written is not None
        assert len(written) == 1
        assert written[0].topic == topic_hint

        found = await knowledge_store.get_knowledge_by_id(written[0].id)
        assert found is not None
        assert found.topic == topic_hint
    finally:
        await engine.dispose()

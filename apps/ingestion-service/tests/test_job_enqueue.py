"""T047: enqueueing a transcript.ingested job on webhook receipt."""

import hashlib
import hmac
import json
import uuid

from db import JobRow, get_engine, get_session_factory, mark_job_done
from fastapi.testclient import TestClient
from sqlalchemy import select

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


def _note_enhanced_payload(meeting_id: str) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "event": "note.enhanced",
        "created_at": "2026-09-24T06:45:53.265Z",
        "data": {
            "meeting": {
                "id": meeting_id,
                "title": "T047 test meeting",
                "note": {"body": "..."},
                "summaries": ["..."],
                "participants": ["Alice"],
                "action_items": [],
            },
            "transcript_text": "Alice: Testing job enqueue.",
        },
    }


async def test_note_enhanced_webhook_enqueues_a_pending_job():
    meeting_id = f"test-meeting-{uuid.uuid4()}"
    client = TestClient(app)

    response = _signed_post(client, _note_enhanced_payload(meeting_id))

    assert response.status_code == 200

    engine = get_engine()
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        result = await session.execute(
            select(JobRow).where(JobRow.type == "transcript.ingested")
        )
        jobs = [
            job
            for job in result.scalars().all()
            if job.payload.get("transcript_id") == meeting_id
        ]
    await engine.dispose()

    assert len(jobs) == 1
    assert jobs[0].status == "pending"
    assert jobs[0].payload == {"transcript_id": meeting_id}

    # dequeue_job() claims the oldest *pending* job globally (libs/db/jobs.py) -
    # a job left pending here would be picked up by, and break, other tests
    # (e.g. libs/db/tests/test_jobs.py) that assume a clean queue. Mark it
    # done so it stops counting as pending once this test is finished with it.
    engine = get_engine()
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        await mark_job_done(session, jobs[0].id)
    await engine.dispose()

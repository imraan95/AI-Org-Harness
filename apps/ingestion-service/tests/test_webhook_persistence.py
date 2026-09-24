"""T046: persisting real Anarlog events (and only real events) on receipt."""

import uuid

from db import get_chunks_by_transcript_id, get_engine, get_session_factory, get_transcript
from fastapi.testclient import TestClient

from ingestion_service.main import app


def _note_enhanced_payload(meeting_id: str) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "event": "note.enhanced",
        "created_at": "2026-09-24T06:45:53.265Z",
        "data": {
            "meeting": {
                "id": meeting_id,
                "title": "T046 test meeting",
                "note": {"body": "..."},
                "summaries": ["..."],
                "participants": ["Alice", "Bob"],
                "action_items": [],
            },
            "transcript_text": "Alice: Three enterprise customers have asked for SSO.",
        },
    }


async def test_note_enhanced_webhook_persists_transcript_and_chunks():
    meeting_id = f"test-meeting-{uuid.uuid4()}"
    client = TestClient(app)

    response = client.post(
        "/webhooks/anarlog", json=_note_enhanced_payload(meeting_id)
    )

    assert response.status_code == 200

    engine = get_engine()
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        transcript = await get_transcript(session, meeting_id)
        chunks = await get_chunks_by_transcript_id(session, meeting_id)
    await engine.dispose()

    assert transcript is not None
    assert transcript.meeting_title == "T046 test meeting"
    assert transcript.attendees == ["Alice", "Bob"]
    assert len(chunks) >= 1


async def test_meeting_completed_webhook_is_acknowledged_but_not_persisted():
    """meeting.completed fires before note.enhanced for the same meeting -
    persisted separately, it would collide on Transcript.id. See main.py's
    _PERSISTABLE_EVENTS comment."""
    meeting_id = f"test-meeting-{uuid.uuid4()}"
    payload = _note_enhanced_payload(meeting_id)
    payload["event"] = "meeting.completed"
    client = TestClient(app)

    response = client.post("/webhooks/anarlog", json=payload)

    assert response.status_code == 200

    engine = get_engine()
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        transcript = await get_transcript(session, meeting_id)
    await engine.dispose()

    assert transcript is None


async def test_webhook_test_event_is_acknowledged_but_not_persisted():
    client = TestClient(app)

    response = client.post(
        "/webhooks/anarlog",
        json={
            "id": f"evt_{uuid.uuid4().hex}",
            "event": "webhook.test",
            "created_at": "2026-09-24T06:45:53.265Z",
            "data": {"message": "This is a test delivery from Anarlog."},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "received"}

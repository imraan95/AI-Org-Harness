import uuid
from datetime import datetime, timezone

import pytest
from shared_schemas import Transcript

from db import get_engine, get_session_factory, get_transcript, insert_transcript


async def test_insert_and_get_transcript_roundtrip():
    engine = get_engine()
    session_factory = get_session_factory(engine)

    transcript = Transcript(
        id=f"test-{uuid.uuid4()}",
        meeting_title="T015 test meeting",
        attendees=["Alice", "Bob"],
        meeting_date=datetime.now(timezone.utc),
        source="test",
        raw_text="Some transcript text.",
    )

    async with session_factory() as session:
        await insert_transcript(session, transcript)

    async with session_factory() as session:
        fetched = await get_transcript(session, transcript.id)

    await engine.dispose()

    assert fetched is not None
    assert fetched.id == transcript.id
    assert fetched.meeting_title == transcript.meeting_title
    assert fetched.attendees == transcript.attendees
    assert fetched.source == transcript.source
    assert fetched.raw_text == transcript.raw_text
    assert fetched.meeting_date.timestamp() == pytest.approx(
        transcript.meeting_date.timestamp()
    )

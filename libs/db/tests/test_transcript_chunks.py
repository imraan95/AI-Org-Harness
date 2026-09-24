import uuid
from datetime import datetime, timezone

from shared_schemas import Transcript, TranscriptChunk

from db import (
    get_chunks_by_transcript_id,
    get_engine,
    get_session_factory,
    insert_transcript,
    insert_transcript_chunks,
)


async def test_insert_and_get_chunks_roundtrip_preserves_count_and_order():
    engine = get_engine()
    session_factory = get_session_factory(engine)

    transcript_id = f"test-{uuid.uuid4()}"
    transcript = Transcript(
        id=transcript_id,
        meeting_title="T016 test meeting",
        attendees=["Alice"],
        meeting_date=datetime.now(timezone.utc),
        source="test",
        raw_text="Some transcript text.",
    )

    chunks = [
        TranscriptChunk(
            id=f"{transcript_id}-chunk-{i}",
            transcript_id=transcript_id,
            text=f"chunk number {i}",
            embedding=[0.1 * i, 0.2 * i, 0.3 * i],
            order=i,
        )
        for i in range(3)
    ]

    async with session_factory() as session:
        await insert_transcript(session, transcript)

    async with session_factory() as session:
        await insert_transcript_chunks(session, transcript_id, chunks)

    async with session_factory() as session:
        fetched = await get_chunks_by_transcript_id(session, transcript_id)

    await engine.dispose()

    assert len(fetched) == 3
    assert [c.order for c in fetched] == [0, 1, 2]
    assert [c.text for c in fetched] == [c.text for c in chunks]

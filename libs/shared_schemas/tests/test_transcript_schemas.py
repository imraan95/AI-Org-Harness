from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared_schemas import Transcript, TranscriptChunk


def test_valid_transcript_constructs():
    transcript = Transcript(
        id="meeting_123",
        meeting_title="Q3 Product Sync",
        attendees=["Alice", "Bob"],
        meeting_date=datetime.now(timezone.utc),
        source="anarlog",
        raw_text="Alice: ... Bob: ...",
    )
    assert transcript.id == "meeting_123"
    assert transcript.attendees == ["Alice", "Bob"]


def test_transcript_missing_field_raises_validation_error():
    with pytest.raises(ValidationError):
        Transcript(
            id="meeting_123",
            # meeting_title omitted on purpose
            attendees=["Alice"],
            meeting_date=datetime.now(timezone.utc),
            source="anarlog",
            raw_text="...",
        )


def test_valid_transcript_chunk_constructs():
    chunk = TranscriptChunk(
        id="chunk_1",
        transcript_id="meeting_123",
        text="Three enterprise customers have asked for SSO.",
        embedding=[0.1, 0.2, 0.3],
        order=0,
    )
    assert chunk.transcript_id == "meeting_123"
    assert chunk.order == 0


def test_transcript_chunk_missing_field_raises_validation_error():
    with pytest.raises(ValidationError):
        TranscriptChunk(
            id="chunk_1",
            # transcript_id omitted on purpose
            text="...",
            embedding=[0.1],
            order=0,
        )

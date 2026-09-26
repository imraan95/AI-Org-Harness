from datetime import datetime, timezone

from ingestion_service import build_transcript_chunks, normalise_anarlog_payload


def _fixture_payload(**overrides):
    payload = {
        "id": "evt_30d1dcbb059a417892be7353ec5e9cd4",
        "event": "note.enhanced",
        "created_at": "2026-09-24T06:45:53.265Z",
        "data": {
            "meeting": {
                "id": "meeting_abc123",
                "title": "Q3 Product Sync",
                "note": {"body": "..."},
                "summaries": ["..."],
                "participants": ["Alice", "Bob"],
                "action_items": [],
            },
            "transcript_text": "Alice: Three enterprise customers have asked for SSO.",
        },
    }
    payload.update(overrides)
    return payload


def test_normalise_produces_a_valid_transcript():
    transcript, _chunk_texts = normalise_anarlog_payload(_fixture_payload())

    assert transcript.id == "meeting_abc123"
    assert transcript.meeting_title == "Q3 Product Sync"
    assert transcript.attendees == ["Alice", "Bob"]
    assert transcript.source == "anarlog"
    assert transcript.raw_text == (
        "Alice: Three enterprise customers have asked for SSO."
    )
    assert transcript.meeting_date == datetime(
        2026, 9, 24, 6, 45, 53, 265000, tzinfo=timezone.utc
    )


def test_normalise_handles_participant_objects_as_well_as_plain_strings():
    payload = _fixture_payload()
    payload["data"]["meeting"]["participants"] = [
        "Alice",
        {"name": "Bob"},
        {"display_name": "Charlie"},
    ]

    transcript, _ = normalise_anarlog_payload(payload)

    assert transcript.attendees == ["Alice", "Bob", "Charlie"]


def test_normalise_chunks_long_transcript_text_into_multiple_pieces():
    payload = _fixture_payload()
    payload["data"]["transcript_text"] = "word " * 100  # 500 chars

    _transcript, chunk_texts = normalise_anarlog_payload(payload, chunk_size=50)

    assert len(chunk_texts) > 1
    assert all(len(chunk) <= 50 for chunk in chunk_texts)
    # No text lost in the split.
    assert "".join(chunk.replace(" ", "") for chunk in chunk_texts) == "word" * 100


def test_normalise_returns_no_chunks_for_empty_transcript_text():
    payload = _fixture_payload()
    payload["data"]["transcript_text"] = ""

    _transcript, chunk_texts = normalise_anarlog_payload(payload)

    assert chunk_texts == []


async def test_build_transcript_chunks_wraps_each_chunk_with_no_embedding():
    # No embedding step needed - nothing in this codebase reads
    # TranscriptChunk.embedding back for anything (no similarity search
    # is ever run against it), so this no longer takes/calls an LLM at
    # all - see build_transcript_chunks's own docstring for why.
    chunks = await build_transcript_chunks(
        "meeting_abc123", ["first chunk", "second chunk"]
    )

    assert len(chunks) == 2
    assert [chunk.order for chunk in chunks] == [0, 1]
    assert all(chunk.transcript_id == "meeting_abc123" for chunk in chunks)
    assert all(chunk.text for chunk in chunks)
    assert all(chunk.embedding == [] for chunk in chunks)

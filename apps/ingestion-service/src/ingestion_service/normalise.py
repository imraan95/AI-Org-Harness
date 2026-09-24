"""T045: convert Anarlog's webhook payload into our own Transcript/
TranscriptChunk types (shared_schemas, from T009).

Two gaps from docs/research/anarlog.md are not yet resolved by a real
`meeting.completed`/`note.enhanced` payload (only `webhook.test` has been
captured live so far) - both handled defensively below, not guessed at
silently:
  - No confirmed field for the meeting's actual date/time, so
    `meeting_date` falls back to the envelope's `created_at` (delivery
    time). Fine for `meeting.completed`; less accurate for
    `note.enhanced`, which can fire well after the meeting.
  - `participants`' exact shape (plain strings vs objects) isn't
    documented; `_participant_name` handles both.
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any
from uuid import uuid4

from llm_router import LLM
from shared_schemas import Transcript, TranscriptChunk

# Arbitrary - no chunking strategy is specified anywhere in the PRD or
# architecture docs. Plain fixed-size, whitespace-respecting splitting;
# revisit if/when retrieval actually needs something smarter (e.g.
# sentence-aware or overlapping chunks).
DEFAULT_CHUNK_SIZE = 2000


def _participant_name(participant: Any) -> str:
    if isinstance(participant, str):
        return participant
    if isinstance(participant, dict):
        return str(
            participant.get("name") or participant.get("display_name") or participant
        )
    return str(participant)


def _parse_timestamp(value: str) -> datetime:
    # datetime.fromisoformat() doesn't accept a trailing "Z" before Python
    # 3.11, and this package targets >=3.10.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalise_anarlog_payload(
    payload: dict[str, Any], *, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> tuple[Transcript, list[str]]:
    """Pure - no I/O. Returns the `Transcript` plus raw chunk text.

    Call `build_transcript_chunks()` separately to turn that chunk text
    into real `TranscriptChunk`s - that step calls an embedding model, so
    it's kept out of this function on purpose.
    """
    data = payload.get("data", {})
    meeting = data.get("meeting", {})
    transcript_text = data.get("transcript_text", "")

    transcript = Transcript(
        id=meeting.get("id") or f"anarlog-{uuid4()}",
        meeting_title=meeting.get("title", ""),
        attendees=[_participant_name(p) for p in meeting.get("participants", [])],
        meeting_date=_parse_timestamp(payload["created_at"]),
        source="anarlog",
        raw_text=transcript_text,
    )
    chunk_texts = (
        textwrap.wrap(transcript_text, width=chunk_size) if transcript_text else []
    )
    return transcript, chunk_texts


async def build_transcript_chunks(
    llm: LLM, transcript_id: str, chunk_texts: list[str]
) -> list[TranscriptChunk]:
    """The I/O half of normalisation: embeds each chunk and wraps it into a
    `TranscriptChunk`. Kept separate from `normalise_anarlog_payload` so
    that function can stay pure and unit-testable without a model.
    """
    chunks: list[TranscriptChunk] = []
    for order, text in enumerate(chunk_texts):
        embedding = await llm.embed(text)
        chunks.append(
            TranscriptChunk(
                id=f"chunk-{uuid4()}",
                transcript_id=transcript_id,
                text=text,
                embedding=embedding,
                order=order,
            )
        )
    return chunks

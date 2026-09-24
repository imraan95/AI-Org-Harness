from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Transcript(BaseModel):
    """A single raw meeting transcript ingested from a source (e.g. Anarlog)."""

    id: str
    meeting_title: str
    attendees: list[str]
    meeting_date: datetime
    source: str
    raw_text: str


class TranscriptChunk(BaseModel):
    """A chunk of a transcript's text, with its embedding, used for retrieval."""

    id: str
    transcript_id: str
    text: str
    embedding: list[float]
    order: int

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TranscriptRow(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    meeting_title: Mapped[str] = mapped_column(Text)
    attendees: Mapped[list[str]] = mapped_column(ARRAY(Text))
    meeting_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)


class TranscriptChunkRow(Base):
    __tablename__ = "transcript_chunks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector, nullable=True)
    order: Mapped[int]


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(Text, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CustomKnowledgeTypeRow(Base):
    __tablename__ = "custom_knowledge_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[str] = mapped_column(Text, default="default")
    key: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class KnowledgeRecordRow(Base):
    __tablename__ = "knowledge_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float]
    source_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    people: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    supersedes: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conflicts_with: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    workspace_id: Mapped[str] = mapped_column(Text, default="default")
    source_id: Mapped[str] = mapped_column(Text, default="unspecified")
    visibility: Mapped[str] = mapped_column(Text, default="internal")
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_level: Mapped[str] = mapped_column(Text, default="standard")
    edited_by: Mapped[str | None] = mapped_column(Text, nullable=True)


class IngestionEventRow(Base):
    __tablename__ = "ingestion_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    transcript_id: Mapped[str | None] = mapped_column(
        ForeignKey("transcripts.id"), nullable=True
    )

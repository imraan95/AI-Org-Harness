from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType
from llm_router import LLM
from openviking_client import OpenVikingClient
from shared_schemas import Transcript

from .confidence import confidence_bucket, score_confidence

logger = logging.getLogger(__name__)


async def _extract(llm: LLM, transcript: Transcript) -> list[dict[str, Any]]:
    """Turn a transcript's text into draft knowledge candidates."""
    return await llm.extract(transcript.raw_text)


async def _retrieve(
    openviking: OpenVikingClient, candidates: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], list[KnowledgeRecord]]]:
    """For each candidate, pull existing knowledge on the same topic."""
    results: list[tuple[dict[str, Any], list[KnowledgeRecord]]] = []
    for candidate in candidates:
        existing = await openviking.get_relevant_knowledge(candidate["topic"])
        results.append((candidate, existing))
    return results


async def _compare(
    llm: LLM,
    candidates_with_existing: list[tuple[dict[str, Any], list[KnowledgeRecord]]],
) -> list[tuple[dict[str, Any], list[KnowledgeRecord], str]]:
    """For each candidate, classify its relationship to existing knowledge as
    one of: new, corroborating, superseding, contradicting.

    When there's no existing knowledge on the topic (T041), the answer is
    "new" by definition - there's nothing to compare against, so this
    skips the LLM call entirely rather than asking a model to compare a
    candidate against an empty list.
    """
    results: list[tuple[dict[str, Any], list[KnowledgeRecord], str]] = []
    for candidate, existing in candidates_with_existing:
        if not existing:
            relationship = "new"
        else:
            relationship = await llm.compare(
                candidate, [record.model_dump() for record in existing]
            )
        results.append((candidate, existing, relationship))
    return results


async def _classify(
    llm: LLM,
    compared: list[tuple[dict[str, Any], list[KnowledgeRecord], str]],
) -> list[dict[str, Any]]:
    """Assign a `type` (via the LLM) and a `confidence` (via PRD §10's
    rules) to each compared candidate.
    """
    classified: list[dict[str, Any]] = []
    for candidate, existing, relationship in compared:
        knowledge_type = await llm.classify(
            candidate["statement"], [t.value for t in KnowledgeType]
        )
        confidence = score_confidence(
            candidate.get("source_context", "casual_conversation")
        )
        classified.append(
            {
                **candidate,
                "existing": existing,
                "relationship": relationship,
                "type": knowledge_type,
                "confidence": confidence,
            }
        )
    return classified


def _determine_status(
    existing: list[KnowledgeRecord], relationship: str, confidence: float
) -> KnowledgeStatus:
    """PRD §9/§17, build-plan T042: decide what status a newly-classified
    candidate is written with.

    - Contradicts existing knowledge -> CONFLICTING. This is a distinct
      status from PENDING_REVIEW (not just "high impact, needs review"),
      so a contradiction is always an explicit conflict record - never
      silently written as a superseding/active record, and never
      resolved by anything in this module (T043).
    - Low-confidence with nothing else corroborating it -> PENDING_REVIEW.
    - Otherwise -> ACTIVE.
    """
    if relationship == "contradicting":
        return KnowledgeStatus.CONFLICTING
    if confidence_bucket(confidence) == "low" and not existing:
        return KnowledgeStatus.PENDING_REVIEW
    return KnowledgeStatus.ACTIVE


async def _write(
    openviking: OpenVikingClient, classified: list[dict[str, Any]]
) -> list[KnowledgeRecord]:
    """Persist each classified candidate to OpenViking.

    High-impact changes are written as `pending_review` or `conflicting`
    rather than `active`, so a human approves/resolves them before
    they're treated as current (PRD §17) - the system never
    auto-publishes or auto-resolves those (T043).
    """
    written: list[KnowledgeRecord] = []
    for item in classified:
        existing = item["existing"]
        relationship = item["relationship"]
        confidence = item["confidence"]

        status = _determine_status(existing, relationship, confidence)
        conflicts_with = (
            [record.id for record in existing]
            if status == KnowledgeStatus.CONFLICTING
            else []
        )

        now = datetime.now(timezone.utc)
        record = KnowledgeRecord(
            id=f"K-{uuid.uuid4()}",
            type=item["type"],
            topic=item["topic"],
            statement=item["statement"],
            status=status,
            confidence=confidence,
            source_ids=item.get("source_ids", []),
            people=item.get("people", []),
            created_at=now,
            observed_at=now,
            last_updated_at=now,
            conflicts_with=conflicts_with,
        )
        await openviking.write_knowledge(record)
        written.append(record)
    return written


async def process_transcript(
    transcript: Transcript, llm: LLM, openviking: OpenVikingClient
) -> list[KnowledgeRecord]:
    """Entry point for the context agent pipeline (PRD §3, §6, §9).

    Runs Extract, Retrieve, Compare, Classify and Write end to end, and
    returns whatever knowledge records were written.
    """
    logger.info("Received transcript %s for processing", transcript.id)

    candidates = await _extract(llm, transcript)
    logger.info(
        "Extracted %d candidate(s) from transcript %s",
        len(candidates),
        transcript.id,
    )

    candidates_with_existing = await _retrieve(openviking, candidates)
    logger.info(
        "Retrieved existing knowledge for %d candidate(s)",
        len(candidates_with_existing),
    )

    compared = await _compare(llm, candidates_with_existing)
    logger.info("Compared %d candidate(s) against existing knowledge", len(compared))

    classified = await _classify(llm, compared)
    logger.info("Classified %d candidate(s)", len(classified))

    written = await _write(openviking, classified)
    logger.info("Wrote %d knowledge record(s)", len(written))
    return written

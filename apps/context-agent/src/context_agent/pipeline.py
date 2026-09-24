from __future__ import annotations

import logging
from typing import Any

from knowledge_model import KnowledgeRecord, KnowledgeType
from llm_router import LLM
from openviking_client import OpenVikingClient
from shared_schemas import Transcript

from .confidence import score_confidence

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
    """
    results: list[tuple[dict[str, Any], list[KnowledgeRecord], str]] = []
    for candidate, existing in candidates_with_existing:
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


async def process_transcript(
    transcript: Transcript, llm: LLM, openviking: OpenVikingClient
) -> None:
    """Entry point for the context agent pipeline (PRD §3, §6, §9).

    Currently runs the Extract, Retrieve, Compare and Classify steps - Write
    is added in a later task.
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

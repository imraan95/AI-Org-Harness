"""Manually runnable demo of the context-agent pipeline (build-plan.md T032,
swapped to the real OpenViking client in T038).

Hardcodes the PRD §6 SSO example: an existing belief already in the harness
("SSO is an occasional customer request"), then a new meeting transcript
that should produce a knowledge update on the same topic.

The LLM stays fake (FakeLLM) so the demo's extract/compare/classify results
are deterministic and match the PRD's own example exactly - only the
knowledge-store side is real here, per build-plan T038 ("context-agent's
dev entrypoint uses the real store; unit tests continue to inject
FakeOpenVikingClient" - this script IS that dev entrypoint). Writes to
whichever store `get_knowledge_store()` resolves to - Postgres by default,
per docs/decisions/0011 (OpenViking has been removed).

Requires a local Supabase instance running (`supabase start`).

Run with:
    uv run python scripts/seed.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from context_agent import process_transcript
from knowledge_model import KnowledgeRecord
from llm_router import FakeLLM
from openviking_client import get_knowledge_store
from shared_schemas import Transcript


async def main() -> None:
    llm = FakeLLM()
    llm.set_next_extract_result(
        [
            {
                "topic": "enterprise_sso",
                "statement": (
                    "Three enterprise customers have asked for SSO; Sales "
                    "considers it a potential deal blocker."
                ),
            }
        ]
    )
    llm.set_next_compare_result("corroborating")
    llm.set_next_classify_result("customer_insight")

    openviking = get_knowledge_store()

    try:
        now = datetime.now(timezone.utc)
        await openviking.write_knowledge(
            KnowledgeRecord(
                id="K-existing-sso",
                type="customer_insight",
                topic="enterprise_sso",
                statement="SSO is an occasional customer request",
                status="active",
                confidence=0.5,
                source_ids=["meeting_july_2026"],
                people=[],
                created_at=now,
                observed_at=now,
                last_updated_at=now,
            )
        )

        transcript = Transcript(
            id="meeting_september_2026",
            meeting_title="September product meeting",
            attendees=["Sales", "Product"],
            meeting_date=now,
            source="seed-script",
            raw_text=(
                "Three enterprise customers have asked for SSO and Sales "
                "says it's becoming a blocker."
            ),
        )

        written = await process_transcript(transcript, llm, openviking)

        print("\n=== Potential knowledge update ===\n")
        for record in written:
            print(f"Topic:\n{record.topic}\n")
            print(f"New evidence:\n{record.statement}\n")
            print(f"Type: {record.type.value}")
            print(f"Confidence: {record.confidence}")
            print(f"Status: {record.status.value}")
            print(f"Source: {transcript.meeting_title}\n")
            print(f"Queryable directly from the knowledge store as id: {record.id}\n")
    finally:
        await openviking.aclose()


if __name__ == "__main__":
    asyncio.run(main())

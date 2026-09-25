"""T065: seeds the exact PRD §15 scenario for the manual Claude walkthrough.

Writes two knowledge records that together reproduce PRD §15's example
almost verbatim:
  - a customer_insight: "SSO has been identified as a recurring enterprise
    customer requirement." (active)
  - a decision: "The latest product decision prioritised onboarding
    improvements over SSO." (status=conflicting, conflicts_with the
    insight above) - this is what makes `format_answer()` add the
    "tension" sentence PRD §15 asks for.

Also inserts real Supabase `transcripts` rows for the insight's evidence,
named to match PRD §15's own evidence list ("3 customer conversations, 2
sales discussions, Product planning meeting, Leadership meeting") - these
only show up as real meeting titles via `get_evidence(insight_id)`
(T058's per-record provenance join), not via the broader tools, which
show a source count instead (see docs/build-plan.md T064's status note).

Requires a running OpenViking (OPENVIKING_API_KEY set) and a running
Supabase (`supabase start`). Run with:
    uv run python scripts/seed_prd15_walkthrough.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from db import get_session_factory, insert_transcript
from knowledge_model import KnowledgeRecord
from openviking_client import RealOpenVikingClient
from shared_schemas import Transcript

_EVIDENCE_MEETING_TITLES = [
    "Customer conversation - Acme Corp",
    "Customer conversation - Globex",
    "Customer conversation - Initech",
    "Sales discussion - EMEA pipeline",
    "Sales discussion - APAC pipeline",
    "Product planning meeting",
    "Leadership meeting",
]


async def main() -> None:
    now = datetime.now(timezone.utc)
    session_factory = get_session_factory()
    transcript_ids: list[str] = []

    async with session_factory() as session:
        for title in _EVIDENCE_MEETING_TITLES:
            transcript_id = f"t065-{uuid.uuid4()}"
            await insert_transcript(
                session,
                Transcript(
                    id=transcript_id,
                    meeting_title=title,
                    attendees=["Sales", "Product"],
                    meeting_date=now,
                    source="seed-script",
                    raw_text="...",
                ),
            )
            transcript_ids.append(transcript_id)

    openviking = RealOpenVikingClient()
    try:
        insight = KnowledgeRecord(
            id=f"K-t065-insight-{uuid.uuid4()}",
            type="customer_insight",
            topic="enterprise_sso",
            statement="SSO has been identified as a recurring enterprise customer requirement.",
            status="active",
            confidence=0.85,
            source_ids=transcript_ids[:5],  # the 3 customer + 2 sales conversations
            people=[],
            created_at=now,
            observed_at=now,
            last_updated_at=now,
        )
        await openviking.write_knowledge(insight)

        decision = KnowledgeRecord(
            id=f"K-t065-decision-{uuid.uuid4()}",
            type="decision",
            topic="enterprise_sso",
            statement="The latest product decision prioritised onboarding improvements over SSO.",
            status="conflicting",
            confidence=0.9,
            source_ids=transcript_ids[5:],  # the planning + leadership meetings
            people=[],
            created_at=now,
            observed_at=now,
            last_updated_at=now,
            conflicts_with=[insight.id],
        )
        await openviking.write_knowledge(decision)
    finally:
        await openviking.aclose()

    print("Seeded the PRD §15 SSO scenario.\n")
    print(f"Customer insight id: {insight.id}")
    print(f"Decision id:         {decision.id}\n")
    print(
        "In Claude Desktop (with mcp-server connected), ask: "
        '"Why aren\'t we building SSO?"'
    )
    print(
        f"To see real evidence meeting titles directly, you can also ask "
        f"for get_evidence with id {insight.id}."
    )


if __name__ == "__main__":
    asyncio.run(main())

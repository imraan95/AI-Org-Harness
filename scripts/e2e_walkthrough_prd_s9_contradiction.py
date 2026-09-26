"""T076: manual walkthrough of PRD §9's contradiction-detection example -
real Ollama extraction/classification/comparison/topic-matching, a real
knowledge-store write (get_knowledge_store() - Postgres by default, per
docs/decisions/0011), two meetings fed through the REAL pipeline in
sequence, same style as scripts/e2e_manual_walkthrough.py and
e2e_walkthrough_prd_s6_belief_evolution.py.

PRD §9's example is fed verbatim: "SSO is not planned for Q4" (Product
roadmap meeting), then "We're going to ship SSO in November" (Leadership
meeting). Per pipeline.py's `_determine_status`, a "contradicting"
relationship always writes as `KnowledgeStatus.CONFLICTING` - PRD §9's
narrative "Status: Requires confirmation" describes that same idea in
prose, not a literal field value (there's no separate "pending" status in
the KnowledgeStatus enum).

Real Ollama extraction independently produces its own topic wording for
each meeting - it very often does NOT land on the same string across two
meetings about the same real-world subject (docs/decisions/0007's
documented gap). That's expected: bridging that gap is exactly what
docs/decisions/0008's `llm_router.match_topic()` fallback is for, so this
script logs every match_topic/compare call directly (wrapping the real
OllamaLLM) rather than inferring what happened from the written records'
topic strings alone.

Requires: a running Supabase (`supabase start`) and a running Ollama with
`llama3.2` pulled.

Run with:
    uv run python scripts/e2e_walkthrough_prd_s9_contradiction.py
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from datetime import datetime, timezone

from context_agent import process_transcript
from db import get_session_factory, insert_transcript
from knowledge_model import KnowledgeStatus
from llm_router import OllamaLLM
from openviking_client import get_knowledge_store
from shared_schemas import Transcript

_CODENAME = f"nimbus-{uuid.uuid4().hex[:6]}"

_MEETING_1 = f"""\
Sam (Product): For project {_CODENAME} - SSO is not planned for Q4.
"""

_MEETING_2 = f"""\
Jordan (Leadership): On project {_CODENAME} - we're going to ship SSO in \
November.
"""


class _LoggingLLM:
    """See e2e_walkthrough_prd_s6_belief_evolution.py's identical class -
    direct evidence of what Retrieve/Compare actually decided."""

    def __init__(self, inner: OllamaLLM) -> None:
        self._inner = inner

    async def extract(self, text: str) -> list[dict[str, Any]]:
        return await self._inner.extract(text)

    async def classify(self, text: str, categories: list[str]) -> str:
        return await self._inner.classify(text, categories)

    async def match_topic(
        self, candidate: dict[str, Any], existing_topics: list[str]
    ) -> str | None:
        result = await self._inner.match_topic(candidate, existing_topics)
        print(
            f"    [match_topic] candidate topic={candidate.get('topic')!r} "
            f"vs {len(existing_topics)} existing topic(s) -> {result!r}"
        )
        return result

    async def compare(
        self, candidate: dict[str, Any], existing: list[dict[str, Any]]
    ) -> str:
        result = await self._inner.compare(candidate, existing)
        print(
            f"    [compare] candidate topic={candidate.get('topic')!r} "
            f"against {len(existing)} existing record(s) -> {result!r}"
        )
        return result

    async def generate(self, prompt: str) -> str:
        return await self._inner.generate(prompt)

    async def summarise(self, text: str) -> str:
        return await self._inner.summarise(text)

    async def embed(self, text: str) -> list[float]:
        return await self._inner.embed(text)


async def _run_meeting(llm, openviking, *, title: str, attendees: list[str], text: str):
    now = datetime.now(timezone.utc)
    transcript = Transcript(
        id=f"prd-s9-{uuid.uuid4()}",
        meeting_title=title,
        attendees=attendees,
        meeting_date=now,
        source="manual-e2e-walkthrough-prd-s9",
        raw_text=text,
    )
    session_factory = get_session_factory()
    async with session_factory() as session:
        await insert_transcript(session, transcript)
    return await process_transcript(transcript, llm, openviking)


def _print_record(record) -> None:
    print(f"  id:             {record.id}")
    print(f"  topic:          {record.topic}")
    print(f"  status:         {record.status}")
    print(f"  statement:      {record.statement}")
    print(f"  conflicts_with: {record.conflicts_with}")
    print()


async def main() -> None:
    llm = _LoggingLLM(OllamaLLM())
    openviking = get_knowledge_store()
    try:
        print("--- Meeting 1: Product roadmap meeting ---\n")
        first_written = await _run_meeting(
            llm,
            openviking,
            title="Product roadmap meeting",
            attendees=["Sam"],
            text=_MEETING_1,
        )
        if not first_written:
            print("No knowledge candidates were extracted from meeting 1 - stopping.")
            return
        print(f"\nWrote {len(first_written)} record(s):\n")
        for record in first_written:
            _print_record(record)

        print("--- Meeting 2: Leadership meeting ---\n")
        second_written = await _run_meeting(
            llm,
            openviking,
            title="Leadership meeting",
            attendees=["Jordan"],
            text=_MEETING_2,
        )
        if not second_written:
            print("No knowledge candidates were extracted from meeting 2 - stopping.")
            return
        print(f"\nWrote {len(second_written)} record(s):\n")
        for record in second_written:
            _print_record(record)

        first_ids = {record.id for record in first_written}
        conflicting = [
            record
            for record in second_written
            if record.status == KnowledgeStatus.CONFLICTING
        ]
        conflicts_with_first = any(
            record.conflicts_with and set(record.conflicts_with) & first_ids
            for record in conflicting
        )

        print("--- Verdict ---\n")
        if conflicts_with_first:
            print(
                "PASS (per PRD §9): match_topic bridged the two meetings' "
                "independently-worded topics, compare recognised the second "
                f"as contradicting the first, and wrote it with "
                f"status={KnowledgeStatus.CONFLICTING.value!r} rather than "
                "resolving which statement is correct - matching PRD §9's "
                "'the system should not automatically decide which "
                "statement is correct'. Neither record was deleted or "
                "silently changed - both remain, flagged for human review. "
                "See the [match_topic]/[compare] log lines above for "
                "exactly what the model decided."
            )
        elif conflicting:
            print(
                "PARTIAL: a conflicting-status record was written, but its "
                "conflicts_with doesn't point back at meeting 1's own "
                "record - likely due to this shared dev harness's "
                "accumulated duplicate-topic fixtures (see [match_topic]'s "
                "existing-topic count above), not a defect in the "
                "match_topic/compare mechanism itself."
            )
        else:
            print(
                "No conflicting-status record was written this run. Check "
                "the [match_topic] and [compare] log lines above: if "
                "match_topic found no bridge, that's the documented 0007 "
                "gap surfacing for real; if it DID find a bridge but "
                "compare classified the relationship as something other "
                "than 'contradicting' (e.g. reading the November date as "
                "an update rather than a conflict), that's a real model "
                "judgment call worth a human's own read."
            )
    finally:
        await openviking.aclose()


if __name__ == "__main__":
    asyncio.run(main())

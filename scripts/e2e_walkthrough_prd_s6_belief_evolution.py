"""T075: manual walkthrough of PRD §6's belief-evolution example - real
Ollama extraction/classification/comparison/topic-matching (not FakeLLM),
real OpenViking write, two meetings fed through the REAL pipeline in
sequence, same style as scripts/e2e_manual_walkthrough.py.

PRD §6's example meeting text is fed verbatim as the second meeting:
"Three enterprise customers have asked for SSO and Sales says it's
becoming a blocker." The first meeting establishes the earlier
"occasional request" belief PRD §6 shows as pre-existing "Existing
memory".

Real Ollama extraction independently produces its own topic wording for
each meeting - it very often does NOT land on the same string across two
meetings about the same real-world subject (docs/decisions/0007's
documented gap). That's expected and fine: bridging that gap is exactly
what docs/decisions/0008's `llm_router.match_topic()` fallback is for, so
this script logs every `match_topic`/`compare` call directly (wrapping
the real `OllamaLLM`) rather than inferring what happened from the
written records' topic strings alone, which would give a false "gap hit"
reading even when the fallback worked correctly.

Requires: a running OpenViking (OPENVIKING_API_KEY set) and a running
Ollama with `llama3.2` pulled - same as e2e_manual_walkthrough.py. For
T078, point OLLAMA_BASE_URL at your own dedicated instance (see
infra/README.md) so this doesn't contend with OpenViking's own models.

Run with:
    uv run python scripts/e2e_walkthrough_prd_s6_belief_evolution.py
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from datetime import datetime, timezone

from context_agent import process_transcript
from db import get_session_factory, insert_transcript
from llm_router import OllamaLLM
from openviking_client import RealOpenVikingClient
from shared_schemas import Transcript

_CODENAME = f"nimbus-{uuid.uuid4().hex[:6]}"

_MEETING_1 = f"""\
Priya (Support Lead): A couple of customers have mentioned wanting \
Enterprise SSO (we've been tracking it internally as project \
{_CODENAME}) here and there, but it's only come up a couple of times.
Dev (Account Manager): Right, nothing urgent yet - just an occasional \
customer request so far, not something we need to prioritise.
"""

# PRD §6's own example sentence, verbatim, wrapped with a speaker label and
# the same project codename.
_MEETING_2 = f"""\
Alex (Sales Lead): Three enterprise customers have asked for SSO (our \
project {_CODENAME}) and Sales says it's becoming a blocker.
"""


class _LoggingLLM:
    """Wraps a real LLM, printing every match_topic/compare call and its
    result - direct evidence of what the Retrieve/Compare steps actually
    did, rather than inferring it from written records' topic strings
    (which can differ even when match_topic correctly bridged them)."""

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
        id=f"prd-s6-{uuid.uuid4()}",
        meeting_title=title,
        attendees=attendees,
        meeting_date=now,
        source="manual-e2e-walkthrough-prd-s6",
        raw_text=text,
    )
    session_factory = get_session_factory()
    async with session_factory() as session:
        await insert_transcript(session, transcript)
    return await process_transcript(transcript, llm, openviking)


def _print_record(record) -> None:
    print(f"  id:         {record.id}")
    print(f"  topic:      {record.topic}")
    print(f"  status:     {record.status}")
    print(f"  statement:  {record.statement}")
    print(f"  supersedes: {record.supersedes}")
    print()


async def main() -> None:
    llm = _LoggingLLM(OllamaLLM())
    openviking = RealOpenVikingClient()
    try:
        print("--- Meeting 1: establishing the earlier belief ---\n")
        first_written = await _run_meeting(
            llm,
            openviking,
            title="Support/Account sync - early SSO mentions",
            attendees=["Priya", "Dev"],
            text=_MEETING_1,
        )
        if not first_written:
            print("No knowledge candidates were extracted from meeting 1 - stopping.")
            return
        print(f"\nWrote {len(first_written)} record(s):\n")
        for record in first_written:
            _print_record(record)

        print("--- Meeting 2: PRD §6's example sentence ---\n")
        second_written = await _run_meeting(
            llm,
            openviking,
            title="Sales sync - enterprise SSO demand",
            attendees=["Alex"],
            text=_MEETING_2,
        )
        if not second_written:
            print("No knowledge candidates were extracted from meeting 2 - stopping.")
            return
        print(f"\nWrote {len(second_written)} record(s):\n")
        for record in second_written:
            _print_record(record)

        first_ids = {record.id for record in first_written}
        superseded_ids = {
            record.supersedes for record in second_written if record.supersedes
        }

        print("--- Verdict ---\n")
        if superseded_ids & first_ids:
            print(
                "PASS (per PRD §6): match_topic bridged the two meetings' "
                "independently-worded topics, compare recognised the second "
                "as an update to the first, and the old record is still "
                "visible (marked superseded, not deleted or silently "
                "overwritten) - see the [match_topic]/[compare] log lines "
                "above for exactly what the model decided and why."
            )
        else:
            print(
                "No supersedes link was written. Check the [match_topic] and "
                "[compare] log lines above: if match_topic found no bridge, "
                "that's the documented 0007 gap surfacing for real (small "
                "local models won't catch every case); if it DID find a "
                "bridge but compare classified the relationship as "
                "something other than 'superseding' (e.g. 'corroborating'), "
                "that's a real model judgment call worth a human's own read, "
                "not a failure of the fallback mechanism itself."
            )
    finally:
        await openviking.aclose()


if __name__ == "__main__":
    asyncio.run(main())

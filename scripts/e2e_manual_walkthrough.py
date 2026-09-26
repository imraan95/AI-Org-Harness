"""One-off manual end-to-end test: a real sample meeting transcript, run
through the REAL pipeline - real Ollama extraction/classification (not
FakeLLM), a real knowledge-store write (get_knowledge_store() - Postgres
by default, per docs/decisions/0011) - so the result can then be queried
live through the connected `harness` MCP server.

Not part of the automated test suite (that's what T074 will be, using
FakeLLM for determinism - see docs/build-plan.md Phase 14). This script
is deliberately closer to the real thing: it inserts a real `transcripts`
row (matching what ingestion-service would have written from a real
webhook) and calls `process_transcript()` directly with `OllamaLLM()`,
skipping only the webhook HTTP hop itself (already covered by T048/T049's
automated tests) - not the extraction/classification/write path, which is
the part this is actually testing.

Uses a deliberately novel topic/scenario (CSV export, not SSO/anything
else already seeded by earlier tasks' tests) so `_retrieve()` finds no
existing knowledge and `_compare()` takes the "new" branch without
calling the LLM - `OllamaLLM.compare()` isn't implemented yet (see
llm_router/ollama.py), so an existing-knowledge collision here would
raise NotImplementedError.

Requires: a running Supabase (`supabase start`), and a running Ollama
with `llama3.2` pulled.

Run with:
    uv run python scripts/e2e_manual_walkthrough.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from context_agent import process_transcript
from db import get_session_factory, insert_transcript
from llm_router import OllamaLLM
from openviking_client import get_knowledge_store
from shared_schemas import Transcript

_SAMPLE_TRANSCRIPT = """\
Priya (Support Lead): We've had another wave of tickets this week asking \
for a way to export their booking data as CSV. It's the third time this \
month a property manager has asked for it directly.
Dev (Account Manager): Yeah, Meridian Resorts brought it up on our call \
yesterday too - they want to pull nightly bookings into their own \
finance spreadsheet instead of re-keying everything by hand.
Priya: Same with Harbourview Apartments last week. They specifically \
asked for CSV, not PDF - they want to open it straight in Excel.
Dev: Sounds like this is becoming a real recurring pattern across \
multiple accounts, not a one-off request.
"""


async def main() -> None:
    now = datetime.now(timezone.utc)
    transcript = Transcript(
        id=f"e2e-manual-{uuid.uuid4()}",
        meeting_title="Support/Account team sync - CSV export requests",
        attendees=["Priya", "Dev"],
        meeting_date=now,
        source="manual-e2e-walkthrough",
        raw_text=_SAMPLE_TRANSCRIPT,
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        await insert_transcript(session, transcript)

    llm = OllamaLLM()
    openviking = get_knowledge_store()
    try:
        written = await process_transcript(transcript, llm, openviking)
    finally:
        await openviking.aclose()

    if not written:
        print("No knowledge candidates were extracted - nothing written.")
        return

    print(f"Wrote {len(written)} knowledge record(s):\n")
    for record in written:
        print(f"  id:        {record.id}")
        print(f"  type:      {record.type}")
        print(f"  topic:     {record.topic}")
        print(f"  status:    {record.status}")
        print(f"  statement: {record.statement}")
        print()

    print(
        "Ask Claude (with the `harness` MCP server connected) something "
        'like: "Are customers asking for CSV export?"'
    )
    print(f"Or drill into one record directly with get_evidence({written[0].id!r}).")


if __name__ == "__main__":
    asyncio.run(main())

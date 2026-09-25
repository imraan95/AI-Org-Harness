"""T061: MCP scaffold + `get_evidence` (PRD §14).
T062: `search_company_context`, `get_recent_decisions`, `get_customer_insights`.
T063: `get_current_strategy`, `get_product_context`, `get_person_context`,
`get_conflicting_information`.
T064: every tool's output is PRD §15-style prose (Current understanding /
Evidence / tension), not raw JSON - see formatting.py.
Post-T065: tool descriptions sharpened (by user decision) so a model
reaches for these tools on its own for company-internal questions,
without needing to be told to "check the harness" explicitly - confirmed
necessary live, when a real Claude Desktop chat asked PRD §15's own
example question and didn't call any tool at all. Descriptions are kept
generic (no company name, no RMS-specific wording) since this app is
meant to scale to any organisation that deploys it, not just this one.

Wraps harness-api as an MCP tool, per docs/architecture.md's
apps/mcp-server design: each tool calls harness-api using the static
service key, and this app holds no state of its own.
"""

from __future__ import annotations

from typing import Callable

from mcp.server.fastmcp import FastMCP

from .client import HarnessAPIClient
from .formatting import format_answer

mcp = FastMCP(
    "harness-mcp-server",
    instructions=(
        "Gives access to this organisation's knowledge harness - a "
        "persistent, continuously updated memory of decisions, strategy, "
        "customer insights, product requirements, people, and known "
        "conflicts, extracted automatically from the organisation's own "
        "meetings. Prefer these tools over general knowledge or "
        "guessing whenever a question is about this organisation's own "
        "internal state: what has been decided, why something is or "
        "isn't happening, what customers have said, who owns what, or "
        "what the current strategy is."
    ),
)

# A factory, not a module-level instance - `HarnessAPIClient()` opens a
# real httpx.AsyncClient at construction time, and tests need to swap in
# one backed by httpx.ASGITransport (talking to an in-process harness-api
# app) instead of a real network server. Production just uses the default.
_client_factory: Callable[[], HarnessAPIClient] = HarnessAPIClient


@mcp.tool()
async def get_evidence(knowledge_id: str) -> str:
    """Look up the full detail and supporting evidence behind one specific
    piece of organisational knowledge already identified in the harness,
    given its id (e.g. an id surfaced by one of this server's other
    tools). Use this to drill into provenance - which real meetings, and
    when - behind a specific fact, decision, or insight."""
    client = _client_factory()
    try:
        record = await client.get_knowledge(knowledge_id)
    finally:
        await client.aclose()
    return format_answer([record])


@mcp.tool()
async def search_company_context() -> str:
    """Search the organisation's entire knowledge harness at once -
    every active decision, strategy, customer insight, product
    requirement, and person record. Use this as the default, broad
    starting point for any open-ended question about the organisation's
    own internal state (e.g. "why aren't we doing X", "what's going on
    with Y"), especially when it's not obviously scoped to just one of
    decisions, strategy, customers, product, or people."""
    client = _client_factory()
    try:
        records = await client.get_context()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_recent_decisions() -> str:
    """Every organisational decision recorded in the knowledge harness -
    what was decided, and the reasoning behind it, extracted from real
    meetings. Use this for questions like "what did we decide about X",
    "has X been decided yet", or "what was the call on X"."""
    client = _client_factory()
    try:
        records = await client.get_decisions()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_customer_insights() -> str:
    """Every customer insight recorded in the knowledge harness - what
    customers have asked for, said, or reacted to, extracted from real
    meetings. Use this for questions about customer demand, feedback, or
    requests, e.g. "what are customers asking for" or "what's the
    feedback on X"."""
    client = _client_factory()
    try:
        records = await client.get_customer_insights()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_current_strategy() -> str:
    """Every strategy record in the knowledge harness - the organisation's
    current stated direction and priorities. Use this for questions like
    "what's our strategy on X" or "are we prioritising X right now"."""
    client = _client_factory()
    try:
        records = await client.get_current_strategy()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_product_context() -> str:
    """Every product requirement recorded in the knowledge harness - what's
    planned, in scope, or roadmapped. Use this for questions like "is X
    planned", "what's in scope for X", or "what does the roadmap say
    about X"."""
    client = _client_factory()
    try:
        records = await client.get_product_context()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_person_context() -> str:
    """Every person record in the knowledge harness - who owns what, who
    said or committed to what, who's responsible for a given area. Use
    this for questions like "who owns X" or "who's responsible for X"."""
    client = _client_factory()
    try:
        records = await client.get_people()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_conflicting_information() -> str:
    """Potential contradictions and pending confirmations currently
    flagged in the knowledge harness - places where recorded
    organisational knowledge disagrees with itself (PRD §16.B). Use this
    for questions like "is there a conflict on X", "why does this seem
    inconsistent", or "what's unresolved right now"."""
    client = _client_factory()
    try:
        records = await client.get_conflicts()
    finally:
        await client.aclose()
    return format_answer(records)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

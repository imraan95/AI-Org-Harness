"""T061: MCP scaffold + `get_evidence` (PRD §14).
T062: `search_company_context`, `get_recent_decisions`, `get_customer_insights`.
T063: `get_current_strategy`, `get_product_context`, `get_person_context`,
`get_conflicting_information`.
T064: every tool's output is PRD §15-style prose (Current understanding /
Evidence / tension), not raw JSON - see formatting.py.

Wraps harness-api as an MCP tool, per docs/architecture.md's
apps/mcp-server design: each tool calls harness-api using the static
service key, and this app holds no state of its own.
"""

from __future__ import annotations

from typing import Callable

from mcp.server.fastmcp import FastMCP

from .client import HarnessAPIClient
from .formatting import format_answer

mcp = FastMCP("harness-mcp-server")

# A factory, not a module-level instance - `HarnessAPIClient()` opens a
# real httpx.AsyncClient at construction time, and tests need to swap in
# one backed by httpx.ASGITransport (talking to an in-process harness-api
# app) instead of a real network server. Production just uses the default.
_client_factory: Callable[[], HarnessAPIClient] = HarnessAPIClient


@mcp.tool()
async def get_evidence(knowledge_id: str) -> str:
    """Fetch a single knowledge record (with its sources) by id, formatted
    as prose with an evidence list."""
    client = _client_factory()
    try:
        record = await client.get_knowledge(knowledge_id)
    finally:
        await client.aclose()
    return format_answer([record])


@mcp.tool()
async def search_company_context() -> str:
    """Every active knowledge record across the whole company harness."""
    client = _client_factory()
    try:
        records = await client.get_context()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_recent_decisions() -> str:
    """Every recorded organisational decision."""
    client = _client_factory()
    try:
        records = await client.get_decisions()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_customer_insights() -> str:
    """Every recorded customer insight."""
    client = _client_factory()
    try:
        records = await client.get_customer_insights()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_current_strategy() -> str:
    """Every recorded strategy record."""
    client = _client_factory()
    try:
        records = await client.get_current_strategy()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_product_context() -> str:
    """Every recorded product requirement."""
    client = _client_factory()
    try:
        records = await client.get_product_context()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_person_context() -> str:
    """Every recorded person record."""
    client = _client_factory()
    try:
        records = await client.get_people()
    finally:
        await client.aclose()
    return format_answer(records)


@mcp.tool()
async def get_conflicting_information() -> str:
    """Potential contradictions / pending confirmation (PRD §16.B)."""
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

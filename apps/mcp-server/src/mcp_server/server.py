"""T061: MCP scaffold + `get_evidence` (PRD §14).
T062: `search_company_context`, `get_recent_decisions`, `get_customer_insights`.

Wraps harness-api as an MCP tool, per docs/architecture.md's
apps/mcp-server design: each tool calls harness-api using the static
service key, and this app holds no state of its own.
"""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from .client import HarnessAPIClient

mcp = FastMCP("harness-mcp-server")

# A factory, not a module-level instance - `HarnessAPIClient()` opens a
# real httpx.AsyncClient at construction time, and tests need to swap in
# one backed by httpx.ASGITransport (talking to an in-process harness-api
# app) instead of a real network server. Production just uses the default.
_client_factory: Callable[[], HarnessAPIClient] = HarnessAPIClient


@mcp.tool()
async def get_evidence(knowledge_id: str) -> dict[str, Any]:
    """Fetch a single knowledge record (with its sources) by id."""
    client = _client_factory()
    try:
        return await client.get_knowledge(knowledge_id)
    finally:
        await client.aclose()


@mcp.tool()
async def search_company_context() -> list[dict[str, Any]]:
    """Every active knowledge record across the whole company harness."""
    client = _client_factory()
    try:
        return await client.get_context()
    finally:
        await client.aclose()


@mcp.tool()
async def get_recent_decisions() -> list[dict[str, Any]]:
    """Every recorded organisational decision."""
    client = _client_factory()
    try:
        return await client.get_decisions()
    finally:
        await client.aclose()


@mcp.tool()
async def get_customer_insights() -> list[dict[str, Any]]:
    """Every recorded customer insight."""
    client = _client_factory()
    try:
        return await client.get_customer_insights()
    finally:
        await client.aclose()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

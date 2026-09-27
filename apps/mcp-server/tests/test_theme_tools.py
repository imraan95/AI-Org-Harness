"""T087: `get_context_for_theme` and `list_available_themes` MCP tools -
closes the gap flagged in docs/build-plan.md's T086 entry: a user-defined
custom theme (T077/T086) could be applied to records but had no generic
way to browse. Calling an in-process harness-api over ASGI, same approach
as test_remaining_query_tools.py. Fixtures are seeded through whichever
knowledge store harness-api is actually configured to use
(get_knowledge_store() - Postgres by default). No skip-guard needed:
matches every other Postgres-backed test in this codebase.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app as harness_api_app
from knowledge_model import KnowledgeRecord
from mcp.shared.memory import create_connected_server_and_client_session
from openviking_client import get_knowledge_store

import mcp_server.server as server_module
from mcp_server.client import HarnessAPIClient
from mcp_server.server import mcp


def _fixture_record(*, statement: str, themes: list[str] | None = None) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t087-{uuid.uuid4()}",
        type="customer_insight",
        topic=f"t087_{uuid.uuid4().hex[:8]}",
        statement=statement,
        status="active",
        confidence=0.75,
        source_ids=[],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
        themes=themes or [],
    )


def _asgi_harness_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=harness_api_app),
        base_url="http://test",
        headers={"x-service-key": HARNESS_API_SERVICE_KEY},
    )


async def _seed(record: KnowledgeRecord) -> None:
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()


async def test_get_context_for_theme_returns_only_records_with_that_theme(monkeypatch):
    theme_key = f"t087_theme_{uuid.uuid4().hex[:8]}"
    tagged = _fixture_record(statement="A tagged statement.", themes=[theme_key])
    untagged = _fixture_record(statement="An untagged statement.")
    await _seed(tagged)
    await _seed(untagged)

    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )

    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "get_context_for_theme", {"theme_key": theme_key}
        )

    assert not result.isError
    answer = result.structuredContent["result"]
    assert answer.startswith("Current understanding:")
    assert "A tagged statement." in answer
    assert "An untagged statement." not in answer


async def test_get_context_for_theme_returns_empty_answer_for_an_unknown_key(monkeypatch):
    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )

    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "get_context_for_theme",
            {"theme_key": f"no-such-theme-{uuid.uuid4().hex[:8]}"},
        )

    assert not result.isError
    assert "Nothing recorded on this yet" in result.structuredContent["result"]


async def test_list_available_themes_includes_the_real_preselected_themes(monkeypatch):
    """Not exact-equality (this shared dev DB's `default` workspace may
    have other custom types added by other tests/sessions) - just
    confirms the 3 preselected themes (migration 20260927100000) show up,
    the same defensive style already used for shared/accumulating dev
    data elsewhere in this codebase."""
    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )

    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("list_available_themes", {})

    assert not result.isError
    answer = result.structuredContent["result"]
    assert "customer_problems: Customer Problems" in answer
    assert "org_decisions: Org Decisions" in answer
    assert "strategic: Strategic" in answer

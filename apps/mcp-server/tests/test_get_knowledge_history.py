"""T067: `get_knowledge_history` MCP tool against a REAL running
OpenViking, calling an in-process harness-api over ASGI - same approach
as test_get_evidence.py. Confirms the tool surfaces the same chain as a
direct REST call to /knowledge/{id}/history (T059), formatted via
`format_history()` (T067) rather than `format_answer()`.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app as harness_api_app
from knowledge_model import KnowledgeRecord
from mcp.shared.memory import create_connected_server_and_client_session
from openviking_client import RealOpenVikingClient

import mcp_server.server as server_module
from mcp_server.client import HarnessAPIClient
from mcp_server.formatting import format_history
from mcp_server.server import mcp

OPENVIKING_BASE_URL = os.environ.get("OPENVIKING_BASE_URL", "http://127.0.0.1:1933")


def _openviking_is_up() -> bool:
    try:
        response = httpx.get(f"{OPENVIKING_BASE_URL}/health", timeout=2.0)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not (_openviking_is_up() and os.environ.get("OPENVIKING_API_KEY")),
    reason="Needs a running OpenViking + OPENVIKING_API_KEY (see docs/research/openviking.md §7).",
)


def _record(*, id: str, topic: str, statement: str, supersedes: str | None = None) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=id,
        type="fact",
        topic=topic,
        statement=statement,
        status="active",
        confidence=0.75,
        source_ids=[],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
        supersedes=supersedes,
    )


def _asgi_harness_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=harness_api_app),
        base_url="http://test",
        headers={"x-service-key": HARNESS_API_SERVICE_KEY},
    )


async def test_get_knowledge_history_matches_a_direct_rest_call(monkeypatch):
    topic = f"t067_{uuid.uuid4().hex[:8]}"
    old_record = _record(
        id=f"K-t067-old-{uuid.uuid4()}",
        topic=topic,
        statement="Old statement, since superseded.",
    )
    new_record = _record(
        id=f"K-t067-new-{uuid.uuid4()}",
        topic=topic,
        statement="New statement that superseded the old one.",
        supersedes=old_record.id,
    )

    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(old_record)
        await openviking.mark_superseded(old_record.id, datetime.now(timezone.utc))
        await openviking.write_knowledge(new_record)
    finally:
        await openviking.aclose()

    # Two independent clients hitting the same in-process app - same
    # reasoning as test_get_evidence.py: the tool's own aclose() must not
    # tear down the client this test uses for its own comparison call.
    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )

    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "get_knowledge_history", {"knowledge_id": new_record.id}
        )

    comparison_client = _asgi_harness_api_client()
    direct_response = await comparison_client.get(f"/knowledge/{new_record.id}/history")
    await comparison_client.aclose()

    assert not result.isError
    assert direct_response.status_code == 200
    assert result.structuredContent["result"] == format_history(direct_response.json())
    # Sanity check the chain itself, not just that the two callers agree.
    assert "New statement that superseded the old one." in result.structuredContent["result"]
    assert "Old statement, since superseded." in result.structuredContent["result"]


async def test_get_knowledge_history_returns_an_error_for_an_unknown_id(monkeypatch):
    asgi_client = _asgi_harness_api_client()
    monkeypatch.setattr(
        server_module, "_client_factory", lambda: HarnessAPIClient(client=asgi_client)
    )

    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "get_knowledge_history", {"knowledge_id": f"K-does-not-exist-{uuid.uuid4()}"}
        )

    await asgi_client.aclose()

    assert result.isError

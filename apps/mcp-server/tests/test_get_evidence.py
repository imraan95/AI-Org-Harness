"""T061: `get_evidence` MCP tool, calling an in-process harness-api over
ASGI (same in-process-HTTP approach harness-api's own tests use via
FastAPI's TestClient - avoids needing a second real uvicorn process
running just for this test). Fixtures are seeded through whichever
knowledge store harness-api is actually configured to use
(get_knowledge_store() - Postgres by default, see openviking_client's
router.py). No skip-guard needed: matches every other Postgres-backed
test in this codebase (e.g. libs/db's own tests).
T064: output is now `format_answer()`'s prose, not raw JSON - compares
against calling that same formatter directly on the REST response.
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
from mcp_server.formatting import format_answer
from mcp_server.server import mcp


def _fixture_record() -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t061-{uuid.uuid4()}",
        type="fact",
        topic=f"t061_{uuid.uuid4().hex[:8]}",
        statement="Fixture statement for T061's get_evidence test.",
        status="active",
        confidence=0.75,
        source_ids=[],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


def _asgi_harness_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=harness_api_app),
        base_url="http://test",
        headers={"x-service-key": HARNESS_API_SERVICE_KEY},
    )


async def test_get_evidence_matches_a_direct_rest_call(monkeypatch):
    record = _fixture_record()
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    # Two independent clients hitting the same in-process app - the tool's
    # own `aclose()` (correct in production, one-shot-per-call) must not
    # tear down the client this test uses for its own comparison call.
    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )

    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("get_evidence", {"knowledge_id": record.id})

    comparison_client = _asgi_harness_api_client()
    direct_response = await comparison_client.get(f"/knowledge/{record.id}")
    await comparison_client.aclose()

    assert not result.isError
    assert direct_response.status_code == 200
    assert result.structuredContent["result"] == format_answer([direct_response.json()])


async def test_get_evidence_returns_an_error_for_an_unknown_id(monkeypatch):
    asgi_client = _asgi_harness_api_client()
    monkeypatch.setattr(
        server_module, "_client_factory", lambda: HarnessAPIClient(client=asgi_client)
    )

    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "get_evidence", {"knowledge_id": f"K-does-not-exist-{uuid.uuid4()}"}
        )

    await asgi_client.aclose()

    assert result.isError

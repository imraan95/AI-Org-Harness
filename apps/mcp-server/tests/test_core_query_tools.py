"""T062: `search_company_context`, `get_recent_decisions`,
`get_customer_insights` against a REAL running OpenViking, calling an
in-process harness-api over ASGI - same approach as test_get_evidence.py.
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


def _fixture_record(*, type: str, statement: str) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t062-{uuid.uuid4()}",
        type=type,
        topic=f"t062_{uuid.uuid4().hex[:8]}",
        statement=statement,
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


def _sorted_by_id(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda r: r["id"])


async def _seed(record: KnowledgeRecord) -> None:
    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()


async def test_search_company_context_matches_a_direct_rest_call(monkeypatch):
    await _seed(_fixture_record(type="decision", statement="We picked X."))

    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("search_company_context", {})

    comparison_client = _asgi_harness_api_client()
    direct_response = await comparison_client.get("/context")
    await comparison_client.aclose()

    assert not result.isError
    assert direct_response.status_code == 200
    # Sorted by id - list ordering isn't a guaranteed contract of these
    # endpoints (grep-based, per docs/research/openviking.md), so this
    # compares the same set of records, not a specific order.
    assert _sorted_by_id(result.structuredContent["result"]) == _sorted_by_id(
        direct_response.json()
    )


async def test_get_recent_decisions_matches_a_direct_rest_call(monkeypatch):
    decision = _fixture_record(type="decision", statement="We picked X.")
    await _seed(decision)

    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("get_recent_decisions", {})

    comparison_client = _asgi_harness_api_client()
    direct_response = await comparison_client.get("/decisions")
    await comparison_client.aclose()

    assert not result.isError
    assert direct_response.status_code == 200
    assert _sorted_by_id(result.structuredContent["result"]) == _sorted_by_id(
        direct_response.json()
    )
    assert decision.id in {r["id"] for r in result.structuredContent["result"]}


async def test_get_customer_insights_matches_a_direct_rest_call(monkeypatch):
    insight = _fixture_record(type="customer_insight", statement="Customers want Y.")
    await _seed(insight)

    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("get_customer_insights", {})

    comparison_client = _asgi_harness_api_client()
    direct_response = await comparison_client.get("/context/customer")
    await comparison_client.aclose()

    assert not result.isError
    assert direct_response.status_code == 200
    assert _sorted_by_id(result.structuredContent["result"]) == _sorted_by_id(
        direct_response.json()
    )
    assert insight.id in {r["id"] for r in result.structuredContent["result"]}

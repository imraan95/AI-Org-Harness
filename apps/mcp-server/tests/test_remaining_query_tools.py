"""T063: `get_current_strategy`, `get_product_context`, `get_person_context`,
`get_conflicting_information` against a REAL running OpenViking, calling an
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


def _fixture_record(*, type: str, statement: str, status: str = "active") -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t063-{uuid.uuid4()}",
        type=type,
        topic=f"t063_{uuid.uuid4().hex[:8]}",
        statement=statement,
        status=status,
        confidence=0.75,
        source_ids=[],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


def _sorted_by_id(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda r: r["id"])


def _asgi_harness_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=harness_api_app),
        base_url="http://test",
        headers={"x-service-key": HARNESS_API_SERVICE_KEY},
    )


async def _seed(record: KnowledgeRecord) -> None:
    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()


async def _run_tool_and_compare(monkeypatch, tool_name: str, rest_path: str) -> tuple[dict, dict]:
    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(tool_name, {})

    comparison_client = _asgi_harness_api_client()
    direct_response = await comparison_client.get(rest_path)
    await comparison_client.aclose()

    assert not result.isError
    assert direct_response.status_code == 200
    assert _sorted_by_id(result.structuredContent["result"]) == _sorted_by_id(
        direct_response.json()
    )
    return result.structuredContent, direct_response.json()


async def test_get_current_strategy_matches_a_direct_rest_call(monkeypatch):
    strategy = _fixture_record(type="strategy", statement="Focus on enterprise.")
    await _seed(strategy)

    structured, _ = await _run_tool_and_compare(
        monkeypatch, "get_current_strategy", "/context/strategy"
    )
    assert strategy.id in {r["id"] for r in structured["result"]}


async def test_get_product_context_matches_a_direct_rest_call(monkeypatch):
    product = _fixture_record(type="product_requirement", statement="Needs SSO.")
    await _seed(product)

    structured, _ = await _run_tool_and_compare(
        monkeypatch, "get_product_context", "/context/product"
    )
    assert product.id in {r["id"] for r in structured["result"]}


async def test_get_person_context_matches_a_direct_rest_call(monkeypatch):
    person = _fixture_record(type="person", statement="Alice owns onboarding.")
    await _seed(person)

    structured, _ = await _run_tool_and_compare(monkeypatch, "get_person_context", "/people")
    assert person.id in {r["id"] for r in structured["result"]}


async def test_get_conflicting_information_matches_a_direct_rest_call(monkeypatch):
    conflicting = _fixture_record(
        type="fact", statement="Two versions disagree.", status="conflicting"
    )
    await _seed(conflicting)

    structured, _ = await _run_tool_and_compare(
        monkeypatch, "get_conflicting_information", "/conflicts"
    )
    assert conflicting.id in {r["id"] for r in structured["result"]}

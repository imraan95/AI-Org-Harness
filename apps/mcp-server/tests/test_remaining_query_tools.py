"""T063: `get_current_strategy`, `get_product_context`, `get_person_context`,
`get_conflicting_information` against a REAL running OpenViking, calling an
in-process harness-api over ASGI - same approach as test_get_evidence.py.
T064: output is now `format_answer()`'s prose - see the note in
test_core_query_tools.py on why these check structure, not exact
string equality against a separately-refetched list.
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


async def _run_tool(monkeypatch, tool_name: str) -> str:
    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(tool_name, {})

    assert not result.isError
    return result.structuredContent["result"]


async def test_get_current_strategy_has_expected_structure(monkeypatch):
    strategy = _fixture_record(type="strategy", statement="Focus on enterprise.")
    await _seed(strategy)

    answer = await _run_tool(monkeypatch, "get_current_strategy")

    assert answer.startswith("Current understanding:")
    assert "Evidence:" in answer
    assert "Focus on enterprise." in answer


async def test_get_product_context_has_expected_structure(monkeypatch):
    product = _fixture_record(type="product_requirement", statement="Needs SSO.")
    await _seed(product)

    answer = await _run_tool(monkeypatch, "get_product_context")

    assert answer.startswith("Current understanding:")
    assert "Evidence:" in answer
    assert "Needs SSO." in answer


async def test_get_person_context_has_expected_structure(monkeypatch):
    person = _fixture_record(type="person", statement="Alice owns onboarding.")
    await _seed(person)

    answer = await _run_tool(monkeypatch, "get_person_context")

    assert answer.startswith("Current understanding:")
    assert "Evidence:" in answer
    assert "Alice owns onboarding." in answer


async def test_get_conflicting_information_has_expected_structure(monkeypatch):
    conflicting = _fixture_record(
        type="fact", statement="Two versions disagree.", status="conflicting"
    )
    await _seed(conflicting)

    answer = await _run_tool(monkeypatch, "get_conflicting_information")

    assert answer.startswith("Current understanding:")
    assert "Evidence:" in answer
    assert "Two versions disagree." in answer
    assert "tension" in answer

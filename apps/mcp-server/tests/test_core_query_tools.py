"""T062: `search_company_context`, `get_recent_decisions`,
`get_customer_insights`, calling an in-process harness-api over ASGI -
same approach as test_get_evidence.py. Fixtures are seeded through
whichever knowledge store harness-api is actually configured to use
(get_knowledge_store() - Postgres by default, see openviking_client's
router.py). No skip-guard needed: matches every other Postgres-backed
test in this codebase (e.g. libs/db's own tests).
T064: output is now `format_answer()`'s prose. These check structure
(sections present, seeded statement/topic appear) rather than exact
string equality against a separately-refetched list - a second live
`GET` can come back in a different order (grep-based, no ordering
guarantee - see docs/research/openviking.md), which would make the
*text* differ even though the underlying records are identical.
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


async def _seed(record: KnowledgeRecord) -> None:
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()


async def test_search_company_context_has_expected_structure(monkeypatch):
    record = _fixture_record(type="decision", statement="We picked X.")
    await _seed(record)

    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("search_company_context", {})

    assert not result.isError
    answer = result.structuredContent["result"]
    assert answer.startswith("Current understanding:")
    assert "Evidence:" in answer
    assert "We picked X." in answer
    assert record.topic in answer


async def test_get_recent_decisions_has_expected_structure(monkeypatch):
    decision = _fixture_record(type="decision", statement="We picked X.")
    await _seed(decision)

    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("get_recent_decisions", {})

    assert not result.isError
    answer = result.structuredContent["result"]
    assert answer.startswith("Current understanding:")
    assert "Evidence:" in answer
    assert "We picked X." in answer


async def test_get_customer_insights_has_expected_structure(monkeypatch):
    insight = _fixture_record(type="customer_insight", statement="Customers want Y.")
    await _seed(insight)

    monkeypatch.setattr(
        server_module,
        "_client_factory",
        lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
    )
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("get_customer_insights", {})

    assert not result.isError
    answer = result.structuredContent["result"]
    assert answer.startswith("Current understanding:")
    assert "Evidence:" in answer
    assert "Customers want Y." in answer

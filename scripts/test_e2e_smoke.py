"""T074: one automated test exercising the full real path - POST a
realistic fixture transcript to ingestion-service, run the context-agent
worker once, then call the MCP tools a real Claude Desktop session would
use (`search_company_context`, `get_evidence`) and confirm the seeded fact
is retrievable with correct provenance (the real meeting title, not a
fixture stand-in).

Follows the same in-process-everything-else pattern as
apps/context-agent/tests/test_worker.py (posting the webhook + running the
worker) and apps/mcp-server/tests/test_core_query_tools.py /
test_get_evidence.py (calling MCP tools over an in-memory session, with
harness-api reached over ASGI rather than a live port). Uses FakeLLM for
the worker's extract/classify step, matching test_worker.py's own e2e
test precedent - real Ollama is only invoked for embeddings, via
ingestion-service's own webhook handler, same as every other real-e2e test
here. The worker writes through whichever knowledge store harness-api is
actually configured to use (get_knowledge_store() - Postgres by default,
see openviking_client's router.py). No skip-guard needed: matches every
other Postgres-backed test in this codebase (e.g. libs/db's own tests).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import httpx
from db import get_engine, get_session_factory
from fastapi.testclient import TestClient
from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app as harness_api_app
from llm_router import FakeLLM
from mcp.shared.memory import create_connected_server_and_client_session
from openviking_client import get_knowledge_store

import mcp_server.server as server_module
from context_agent import run_worker_once
from ingestion_service.main import ANARLOG_WEBHOOK_SECRET, app as ingestion_app
from mcp_server.client import HarnessAPIClient
from mcp_server.server import mcp


def _signed_post(client: TestClient, payload: dict):
    body = json.dumps(payload).encode()
    signature = (
        "sha256="
        + hmac.new(ANARLOG_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    )
    return client.post(
        "/webhooks/anarlog",
        content=body,
        headers={"content-type": "application/json", "x-anarlog-signature": signature},
    )


def _note_enhanced_payload(meeting_id: str, meeting_title: str, topic_hint: str) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "event": "note.enhanced",
        "created_at": "2026-09-24T06:45:53.265Z",
        "data": {
            "meeting": {
                "id": meeting_id,
                "title": meeting_title,
                "note": {"body": "..."},
                "summaries": ["..."],
                "participants": ["Priya"],
                "action_items": [],
            },
            "transcript_text": f"Priya: Testing the full T074 smoke path for {topic_hint}.",
        },
    }


def _asgi_harness_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=harness_api_app),
        base_url="http://test",
        headers={"x-service-key": HARNESS_API_SERVICE_KEY},
    )


async def test_full_path_from_webhook_to_mcp_tools_with_correct_provenance(monkeypatch):
    run_id = uuid.uuid4().hex[:8]
    topic_hint = f"t074_smoke_{run_id}"
    meeting_id = f"t074-meeting-{uuid.uuid4()}"
    meeting_title = f"T074 smoke test meeting {run_id}"

    # 1. Webhook in - persists the transcript and enqueues a job, exactly
    # as a real Anarlog delivery would.
    ingestion_client = TestClient(ingestion_app)
    response = _signed_post(
        ingestion_client, _note_enhanced_payload(meeting_id, meeting_title, topic_hint)
    )
    assert response.status_code == 200

    # 2. Worker runs once - claims that job, extracts (via FakeLLM, so
    # this doesn't also depend on a live, uncontended Ollama - see T078),
    # and writes the resulting record to a REAL OpenViking.
    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result(
        [{"topic": topic_hint, "statement": f"Confirmed the smoke path works for {topic_hint}."}]
    )
    fake_llm.set_next_classify_result("fact")
    openviking = get_knowledge_store()

    engine = get_engine()
    session_factory = get_session_factory(engine)
    try:
        async with session_factory() as session:
            written = await run_worker_once(session, fake_llm, openviking)

        assert written is not None
        assert len(written) == 1
        record = written[0]
        assert record.topic == topic_hint

        # 3. The same MCP tools a real Claude Desktop session calls can
        # find it via a broad, untargeted search...
        monkeypatch.setattr(
            server_module,
            "_client_factory",
            lambda: HarnessAPIClient(client=_asgi_harness_api_client()),
        )
        async with create_connected_server_and_client_session(mcp) as client:
            search_result = await client.call_tool("search_company_context", {})
            evidence_result = await client.call_tool(
                "get_evidence", {"knowledge_id": record.id}
            )

        assert not search_result.isError
        search_answer = search_result.structuredContent["result"]
        assert "Confirmed the smoke path works" in search_answer
        assert topic_hint in search_answer

        # ...and, drilling into that specific record, its evidence names
        # the REAL meeting this fact came from - not just a source count -
        # confirming provenance survived the whole webhook -> worker ->
        # OpenViking -> harness-api -> MCP round trip intact.
        assert not evidence_result.isError
        evidence_answer = evidence_result.structuredContent["result"]
        assert "Confirmed the smoke path works" in evidence_answer
        assert meeting_title in evidence_answer
    finally:
        await openviking.aclose()
        await engine.dispose()

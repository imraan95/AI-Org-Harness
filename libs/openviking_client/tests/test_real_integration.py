"""Integration test against a REAL, running OpenViking service (T035).

Unlike every other test in this repo, this one is NOT a fake/unit test - it
makes real HTTP calls to the container started in infra/docker-compose.yml.
It skips itself automatically if that service isn't reachable, so
`uv run pytest --all-packages` still passes on a machine with nothing
running (e.g. CI, or a laptop that hasn't started the container yet).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from knowledge_model import KnowledgeRecord
from openviking_client import RealOpenVikingClient

BASE_URL = os.environ.get("OPENVIKING_BASE_URL", "http://127.0.0.1:1933")


def _service_is_up() -> bool:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=2.0)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _service_is_up(),
    reason=(
        "No OpenViking service reachable at "
        f"{BASE_URL} - start it with "
        "`docker compose -f infra/docker-compose.yml up openviking`"
    ),
)


def _knowledge_record() -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-{uuid.uuid4()}",
        type="customer_insight",
        topic="enterprise_sso",
        statement="Three enterprise customers have asked for SSO.",
        status="active",
        confidence=0.6,
        source_ids=["meeting_test"],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


async def test_write_then_read_back_by_id_round_trips():
    client = RealOpenVikingClient()
    record = _knowledge_record()

    await client.write_knowledge(record)
    fetched = await client.get_knowledge_by_id(record.id)

    assert fetched == record

    await client.aclose()


async def test_get_knowledge_by_id_returns_none_for_unknown_id():
    client = RealOpenVikingClient()

    fetched = await client.get_knowledge_by_id(f"K-{uuid.uuid4()}")

    assert fetched is None

    await client.aclose()

"""T050: GET /knowledge/{id} against a REAL running OpenViking.
T051: same endpoint, now behind a real Supabase Auth token.

Skips itself if OpenViking isn't reachable, OPENVIKING_API_KEY isn't set,
or SUPABASE_SECRET_KEY/SUPABASE_PUBLISHABLE_KEY aren't set (needed to
create a real test user and sign them in via Supabase Auth's own API -
see docs/build-plan.md T051's own wording: "generated via the Supabase
Auth admin API in the test setup", not a hand-crafted token).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from knowledge_model import KnowledgeRecord
from openviking_client import RealOpenVikingClient

from harness_api.main import app

OPENVIKING_BASE_URL = os.environ.get("OPENVIKING_BASE_URL", "http://127.0.0.1:1933")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY")


def _openviking_is_up() -> bool:
    try:
        response = httpx.get(f"{OPENVIKING_BASE_URL}/health", timeout=2.0)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not (
        _openviking_is_up()
        and os.environ.get("OPENVIKING_API_KEY")
        and SUPABASE_SECRET_KEY
        and SUPABASE_PUBLISHABLE_KEY
    ),
    reason=(
        "Needs a running OpenViking + OPENVIKING_API_KEY (see "
        "docs/research/openviking.md §7), and SUPABASE_SECRET_KEY/"
        "SUPABASE_PUBLISHABLE_KEY set from `supabase status` to create a "
        "real test user via Supabase Auth."
    ),
)


def _fixture_record(record_id: str) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=record_id,
        type="fact",
        topic=f"harness_api_t050_{uuid.uuid4().hex[:8]}",
        statement="Fixture statement for T050's GET /knowledge/{id} test.",
        status="active",
        confidence=0.75,
        source_ids=["meeting_fixture"],
        people=["Alice"],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


def _create_and_sign_in_test_user() -> str:
    """Creates a real, email-confirmed Supabase Auth user via the admin
    API, signs them in, and returns their real access token."""
    email = f"t051-{uuid.uuid4().hex}@example.com"
    password = uuid.uuid4().hex

    create_response = httpx.post(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        },
        json={"email": email, "password": password, "email_confirm": True},
        timeout=10.0,
    )
    create_response.raise_for_status()

    token_response = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": SUPABASE_PUBLISHABLE_KEY},
        json={"email": email, "password": password},
        timeout=10.0,
    )
    token_response.raise_for_status()
    return token_response.json()["access_token"]


async def test_get_knowledge_by_id_returns_a_seeded_record():
    record_id = f"K-test-{uuid.uuid4()}"
    record = _fixture_record(record_id)

    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    token = _create_and_sign_in_test_user()
    client = TestClient(app)
    response = client.get(
        f"/knowledge/{record_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == record_id
    assert body["topic"] == record.topic
    assert body["statement"] == record.statement
    assert body["status"] == "active"


def test_get_knowledge_by_id_returns_404_for_unknown_id():
    token = _create_and_sign_in_test_user()
    client = TestClient(app)
    response = client.get(
        f"/knowledge/K-does-not-exist-{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_get_knowledge_by_id_returns_401_without_a_token():
    client = TestClient(app)
    response = client.get(f"/knowledge/K-does-not-exist-{uuid.uuid4()}")

    assert response.status_code == 401


def test_get_knowledge_by_id_returns_401_with_a_garbage_token():
    client = TestClient(app)
    response = client.get(
        f"/knowledge/K-does-not-exist-{uuid.uuid4()}",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401

"""T054: GET /context, /context/product, /context/customer,
/context/strategy, seeding fixtures through whichever knowledge store
harness-api is actually configured to use (get_knowledge_store() -
Postgres by default, see openviking_client's router.py). No skip-guard
needed: matches every other Postgres-backed test in this codebase (e.g.
libs/db's own tests).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from knowledge_model import KnowledgeRecord
from openviking_client import get_knowledge_store

from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app

_AUTH_HEADERS = {"x-service-key": HARNESS_API_SERVICE_KEY}


def _fixture_record(
    *, type: str, topic: str, statement: str, themes: list[str] | None = None
) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t054-{uuid.uuid4()}",
        type=type,
        topic=topic,
        statement=statement,
        status="active",
        confidence=0.75,
        source_ids=["meeting_fixture"],
        people=["Alice"],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
        themes=themes or [],
    )


async def _seed(record: KnowledgeRecord) -> None:
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()


async def test_context_returns_records_of_mixed_types():
    run_id = uuid.uuid4().hex[:8]
    product = _fixture_record(
        type="product_requirement", topic=f"t054_product_{run_id}", statement="Needs X."
    )
    strategy = _fixture_record(
        type="strategy", topic=f"t054_strategy_{run_id}", statement="Focus on Y."
    )
    await _seed(product)
    await _seed(strategy)

    client = TestClient(app)
    response = client.get("/context", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert {product.id, strategy.id}.issubset(ids)


async def test_context_product_returns_only_product_requirement_records():
    run_id = uuid.uuid4().hex[:8]
    product = _fixture_record(
        type="product_requirement", topic=f"t054_product2_{run_id}", statement="Needs X."
    )
    strategy = _fixture_record(
        type="strategy", topic=f"t054_strategy2_{run_id}", statement="Focus on Y."
    )
    await _seed(product)
    await _seed(strategy)

    client = TestClient(app)
    response = client.get("/context/product", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert product.id in ids
    assert strategy.id not in ids


async def test_context_customer_returns_only_customer_insight_records():
    run_id = uuid.uuid4().hex[:8]
    customer = _fixture_record(
        type="customer_insight", topic=f"t054_customer_{run_id}", statement="Wants Z."
    )
    strategy = _fixture_record(
        type="strategy", topic=f"t054_strategy3_{run_id}", statement="Focus on Y."
    )
    await _seed(customer)
    await _seed(strategy)

    client = TestClient(app)
    response = client.get("/context/customer", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert customer.id in ids
    assert strategy.id not in ids


async def test_context_strategy_returns_only_strategy_records():
    run_id = uuid.uuid4().hex[:8]
    customer = _fixture_record(
        type="customer_insight", topic=f"t054_customer2_{run_id}", statement="Wants Z."
    )
    strategy = _fixture_record(
        type="strategy", topic=f"t054_strategy4_{run_id}", statement="Focus on Y."
    )
    await _seed(customer)
    await _seed(strategy)

    client = TestClient(app)
    response = client.get("/context/strategy", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert strategy.id in ids
    assert customer.id not in ids


async def test_context_theme_returns_only_records_tagged_with_that_theme_key():
    """T087: a generic route, not one hardcoded per fixed built-in type -
    works for any user-defined theme key without a code change."""
    run_id = uuid.uuid4().hex[:8]
    theme_key = f"t087_theme_{run_id}"
    tagged = _fixture_record(
        type="customer_insight",
        topic=f"t087_tagged_{run_id}",
        statement="A tagged statement.",
        themes=[theme_key, "some_other_theme"],
    )
    untagged = _fixture_record(
        type="customer_insight",
        topic=f"t087_untagged_{run_id}",
        statement="An untagged statement.",
    )
    await _seed(tagged)
    await _seed(untagged)

    client = TestClient(app)
    response = client.get(f"/context/theme/{theme_key}", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert tagged.id in ids
    assert untagged.id not in ids


def test_context_theme_returns_empty_list_for_an_unknown_key():
    """An unknown/mistyped theme key is zero matches, not an error - same
    as any other list endpoint with nothing to return."""
    client = TestClient(app)
    response = client.get(
        f"/context/theme/no-such-theme-{uuid.uuid4().hex[:8]}",
        headers=_AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_context_returns_401_without_a_token_or_service_key():
    client = TestClient(app)
    response = client.get("/context")

    assert response.status_code == 401


def test_context_theme_returns_401_without_a_token_or_service_key():
    client = TestClient(app)
    response = client.get("/context/theme/anything")

    assert response.status_code == 401

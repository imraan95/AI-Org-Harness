"""T077: GET/POST /taxonomy/types, DELETE /taxonomy/types/{key}.

These only need a real local Postgres (same assumption as libs/db's own
tests) - no OpenViking skip-guard needed, unlike most of this test suite.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app

_AUTH_HEADERS = {"x-service-key": HARNESS_API_SERVICE_KEY}


def test_get_taxonomy_types_includes_the_12_built_ins():
    client = TestClient(app)
    response = client.get("/taxonomy/types", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    builtin_keys = {t["key"] for t in body if t["builtin"]}
    assert builtin_keys == {
        "decision",
        "fact",
        "customer_insight",
        "strategy",
        "product_requirement",
        "process",
        "policy",
        "person",
        "ownership",
        "action",
        "hypothesis",
        "conflict",
    }


def test_create_then_list_then_delete_a_custom_type():
    client = TestClient(app)
    key = f"t077_{uuid.uuid4().hex[:8]}"

    create_response = client.post(
        "/taxonomy/types",
        headers=_AUTH_HEADERS,
        json={"key": key, "label": "Meeting Notes"},
    )
    assert create_response.status_code == 201
    assert create_response.json() == {
        "key": key,
        "label": "Meeting Notes",
        "builtin": False,
    }

    list_response = client.get("/taxonomy/types", headers=_AUTH_HEADERS)
    custom_keys = {t["key"] for t in list_response.json() if not t["builtin"]}
    assert key in custom_keys

    delete_response = client.delete(f"/taxonomy/types/{key}", headers=_AUTH_HEADERS)
    assert delete_response.status_code == 204

    list_after = client.get("/taxonomy/types", headers=_AUTH_HEADERS)
    custom_keys_after = {t["key"] for t in list_after.json() if not t["builtin"]}
    assert key not in custom_keys_after


def test_create_taxonomy_type_rejects_a_built_in_key():
    client = TestClient(app)
    response = client.post(
        "/taxonomy/types",
        headers=_AUTH_HEADERS,
        json={"key": "decision", "label": "Decision"},
    )
    assert response.status_code == 409


def test_delete_taxonomy_type_rejects_a_built_in_key():
    client = TestClient(app)
    response = client.delete("/taxonomy/types/decision", headers=_AUTH_HEADERS)
    assert response.status_code == 400


def test_delete_taxonomy_type_returns_404_for_unknown_custom_key():
    client = TestClient(app)
    response = client.delete(
        f"/taxonomy/types/nope-{uuid.uuid4().hex[:8]}", headers=_AUTH_HEADERS
    )
    assert response.status_code == 404


def test_get_taxonomy_types_returns_401_without_a_token_or_service_key():
    client = TestClient(app)
    response = client.get("/taxonomy/types")

    assert response.status_code == 401

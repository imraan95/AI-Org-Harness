"""T061: GET /health - unauthenticated liveness check.

No skip-guard needed - this doesn't touch OpenViking or Supabase at all.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from harness_api.main import app


def test_health_returns_ok_without_any_auth():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

"""T061: a thin HTTP client for calling harness-api with the static
service key (T052) - the same "one trusted workspace" auth every other
non-user caller uses.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_HARNESS_API_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_SERVICE_KEY = "dev-service-key-placeholder-changeme"


def _base_url() -> str:
    return os.environ.get("HARNESS_API_BASE_URL", DEFAULT_HARNESS_API_BASE_URL)


def _service_key() -> str:
    # Must match whatever harness-api itself is configured with
    # (HARNESS_API_SERVICE_KEY) - same env var name, read independently
    # here since this app has no import dependency on harness_api.
    return os.environ.get("HARNESS_API_SERVICE_KEY", DEFAULT_SERVICE_KEY)


class HarnessAPIClient:
    """Talks to a real, running harness-api over HTTP.

    Accepts an injected `httpx.AsyncClient` (e.g. one built on
    `httpx.ASGITransport` in tests, to talk to an in-process app instead of
    a real network server) - same shape as `RealOpenVikingClient`.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=_base_url(),
            headers={"x-service-key": _service_key()},
            timeout=30.0,
        )

    async def get_knowledge(self, knowledge_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/knowledge/{knowledge_id}")
        response.raise_for_status()
        return response.json()

    async def _get_list(self, path: str) -> list[dict[str, Any]]:
        response = await self._client.get(path)
        response.raise_for_status()
        return response.json()

    async def get_context(self) -> list[dict[str, Any]]:
        return await self._get_list("/context")

    async def get_decisions(self) -> list[dict[str, Any]]:
        return await self._get_list("/decisions")

    async def get_customer_insights(self) -> list[dict[str, Any]]:
        return await self._get_list("/context/customer")

    async def aclose(self) -> None:
        await self._client.aclose()

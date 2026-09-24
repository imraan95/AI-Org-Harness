from __future__ import annotations

import os
from typing import Any

import httpx

from .interface import LLM

DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_FRONTIER_MODEL = "claude-sonnet-5"


class FrontierLLM(LLM):
    """Calls a frontier API (Anthropic) - optional, used only when an API
    key is configured. See `get_llm()` for the selection logic.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model or os.environ.get(
            "FRONTIER_MODEL", DEFAULT_FRONTIER_MODEL
        )
        self._client = client or httpx.AsyncClient(
            base_url=base_url or DEFAULT_ANTHROPIC_BASE_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=60.0,
        )

    async def generate(self, prompt: str) -> str:
        response = await self._client.post(
            "/v1/messages",
            json={
                "model": self._model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    async def extract(self, text: str) -> list[dict[str, Any]]:
        raise NotImplementedError("FrontierLLM.extract is not wired up yet")

    async def classify(self, text: str, categories: list[str]) -> str:
        raise NotImplementedError("FrontierLLM.classify is not wired up yet")

    async def compare(
        self, candidate: dict[str, Any], existing: list[dict[str, Any]]
    ) -> str:
        raise NotImplementedError("FrontierLLM.compare is not wired up yet")

    async def summarise(self, text: str) -> str:
        raise NotImplementedError("FrontierLLM.summarise is not wired up yet")

    async def embed(self, text: str) -> list[float]:
        # Anthropic has no embeddings API - callers that need real
        # embeddings should use OllamaLLM directly, regardless of which
        # backend get_llm() returns for the other tasks.
        raise NotImplementedError("FrontierLLM.embed is not supported - use OllamaLLM")

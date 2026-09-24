from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .interface import LLM

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"
# Already pulled locally as part of T035's OpenViking setup (its own
# embedding config), so re-using it here needs no extra download.
DEFAULT_OLLAMA_EMBEDDING_MODEL = "qwen3-embedding:0.6b"


class OllamaLLM(LLM):
    """Calls a local Ollama server for the cheap tasks (extract, classify).

    `generate`/`compare`/`summarise` aren't wired up yet - those are decided
    by the model router (later tasks), which may send them to a different
    backend/model entirely.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL
        )
        self._model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self._embedding_model = os.environ.get(
            "OLLAMA_EMBEDDING_MODEL", DEFAULT_OLLAMA_EMBEDDING_MODEL
        )
        # Local model calls (especially a cold start, while Ollama loads the
        # model into memory) can take a lot longer than httpx's 5s default.
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url, timeout=120.0
        )

    async def _call(self, prompt: str, *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if json_mode:
            # Ollama's JSON mode constrains sampling so the output is always
            # syntactically valid JSON - small models otherwise sometimes
            # produce near-JSON with a missing brace/comma.
            payload["format"] = "json"

        response = await self._client.post("/api/generate", json=payload)
        response.raise_for_status()
        return response.json()["response"]

    async def extract(self, text: str) -> list[dict[str, Any]]:
        prompt = (
            "Extract organisational knowledge candidates from this meeting "
            "transcript. Reply with ONLY a JSON object of the form "
            '{"candidates": [{"topic": "...", "statement": "..."}]}, '
            "listing one entry per candidate you find.\n\n"
            f"Transcript:\n{text}"
        )
        raw = await self._call(prompt, json_mode=True)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed.get("candidates", [])
        return parsed

    async def classify(self, text: str, categories: list[str]) -> str:
        prompt = (
            "Classify the following text into exactly one of these "
            f"categories: {', '.join(categories)}. Reply with ONLY the "
            f"category name, nothing else.\n\nText:\n{text}"
        )
        raw = await self._call(prompt)
        return raw.strip()

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError("OllamaLLM.generate is not wired up yet")

    async def compare(
        self, candidate: dict[str, Any], existing: list[dict[str, Any]]
    ) -> str:
        raise NotImplementedError("OllamaLLM.compare is not wired up yet")

    async def summarise(self, text: str) -> str:
        raise NotImplementedError("OllamaLLM.summarise is not wired up yet")

    async def embed(self, text: str) -> list[float]:
        response = await self._client.post(
            "/api/embeddings",
            json={"model": self._embedding_model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]

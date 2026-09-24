from __future__ import annotations

from typing import Any

from .interface import LLM


class FakeLLM(LLM):
    """Test double returning configurable canned responses.

    Never calls a real model - used everywhere in tests so the rest of the
    codebase can be exercised without a live LLM backend.
    """

    def __init__(self) -> None:
        self._next_generate_result: str = ""
        self._next_extract_result: list[dict[str, Any]] = []
        self._next_classify_result: str = ""
        self._next_compare_result: str = ""
        self._next_summarise_result: str = ""

    def set_next_generate_result(self, result: str) -> None:
        self._next_generate_result = result

    def set_next_extract_result(self, result: list[dict[str, Any]]) -> None:
        self._next_extract_result = result

    def set_next_classify_result(self, result: str) -> None:
        self._next_classify_result = result

    def set_next_compare_result(self, result: str) -> None:
        self._next_compare_result = result

    def set_next_summarise_result(self, result: str) -> None:
        self._next_summarise_result = result

    async def generate(self, prompt: str) -> str:
        return self._next_generate_result

    async def extract(self, text: str) -> list[dict[str, Any]]:
        return self._next_extract_result

    async def classify(self, text: str, categories: list[str]) -> str:
        return self._next_classify_result

    async def compare(
        self, candidate: dict[str, Any], existing: list[dict[str, Any]]
    ) -> str:
        return self._next_compare_result

    async def summarise(self, text: str) -> str:
        return self._next_summarise_result

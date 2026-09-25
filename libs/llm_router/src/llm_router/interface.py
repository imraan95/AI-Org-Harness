from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLM(ABC):
    """Model-agnostic interface for every LLM-backed operation (PRD §11).

    Concrete backends (open-weight, frontier API, or a test fake) implement
    this interface; nothing else in the codebase is allowed to call a model
    provider directly.
    """

    @abstractmethod
    async def generate(self, prompt: str) -> str: ...

    @abstractmethod
    async def extract(self, text: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def classify(self, text: str, categories: list[str]) -> str: ...

    @abstractmethod
    async def compare(
        self, candidate: dict[str, Any], existing: list[dict[str, Any]]
    ) -> str: ...

    @abstractmethod
    async def match_topic(
        self, candidate: dict[str, Any], existing_topics: list[str]
    ) -> str | None: ...

    @abstractmethod
    async def summarise(self, text: str) -> str: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

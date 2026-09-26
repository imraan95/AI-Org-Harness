from __future__ import annotations

import os

from .interface import OpenVikingClient
from .postgres import PostgresOpenVikingClient
from .real import RealOpenVikingClient


def get_knowledge_store() -> OpenVikingClient:
    """Return the configured knowledge storage backend.

    Defaults to the Postgres-backed store (`PostgresOpenVikingClient` - see
    its own docstring for why: OpenViking's semantic search is unused since
    docs/decisions/0008, so all it was doing for us was file storage plus
    glob/grep pattern matching, which a plain table does without the
    256-match cap, the AGPL dependency, or a second Docker service).
    OpenViking is opt-in only, via `KNOWLEDGE_STORE=openviking` - mirrors
    `llm_router.get_llm()`'s own "opt-in, not default" pattern for the
    frontier LLM backend.
    """
    backend = os.environ.get("KNOWLEDGE_STORE", "postgres")
    if backend == "openviking":
        return RealOpenVikingClient()
    return PostgresOpenVikingClient()

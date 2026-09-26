from __future__ import annotations

from .interface import OpenVikingClient
from .postgres import PostgresOpenVikingClient


def get_knowledge_store() -> OpenVikingClient:
    """Return the configured knowledge storage backend.

    Per docs/decisions/0011-remove-openviking-entirely.md: OpenViking has
    been removed from the codebase (was previously an opt-in alternative
    to this Postgres-backed store - see docs/decisions/0009). This always
    returns `PostgresOpenVikingClient`.

    Kept as a function, not a direct constructor call at each use site, so
    a different storage backend can be swapped in later by changing this
    one place - same reasoning as `llm_router.get_llm()`.
    """
    return PostgresOpenVikingClient()

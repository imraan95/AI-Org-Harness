from __future__ import annotations

import os
import re

import httpx

from knowledge_model import KnowledgeRecord, KnowledgeStatus

from .interface import OpenVikingClient

DEFAULT_BASE_URL = "http://127.0.0.1:1933"
KNOWLEDGE_ROOT = "viking://resources/knowledge"


def _topic_slug(topic: str) -> str:
    """Make a topic safe to use as a Viking URI path segment.

    Our own pipeline already produces snake_case topics (e.g.
    "enterprise_sso"), but nothing guarantees that forever, and a raw topic
    with spaces/slashes would break the URI. Lowercase, replace anything
    that isn't alphanumeric/underscore/hyphen with "_", collapse repeats.
    """
    slug = re.sub(r"[^a-z0-9_-]+", "_", topic.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "untitled"


class OpenVikingHTTPError(RuntimeError):
    """Raised when OpenViking's API returns an error envelope."""


class RealOpenVikingClient(OpenVikingClient):
    """Talks to a real, running OpenViking service over HTTP.

    Design decision (see docs/research/openviking.md §4 and prd.md §12):
    we don't use OpenViking's own session/memory-extraction feature. Every
    `KnowledgeRecord` our own `context-agent` has already classified is
    written as a plain JSON file under `viking://resources/knowledge/...`,
    and read back the same way - OpenViking is used purely as a
    semantic-searchable file store, not as a second extraction pipeline.

    `write_knowledge`, `get_knowledge_by_id` (T035), and
    `get_relevant_knowledge` (T036) are implemented here.
    `list_conflicts`/`update_knowledge_status` (T037) are implemented in
    a later task.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url or os.environ.get(
            "OPENVIKING_BASE_URL", DEFAULT_BASE_URL
        )
        self._api_key = api_key or os.environ.get("OPENVIKING_API_KEY")
        headers = {"X-API-Key": self._api_key} if self._api_key else {}
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url, headers=headers, timeout=60.0
        )

    def _record_uri(self, record: KnowledgeRecord) -> str:
        return f"{KNOWLEDGE_ROOT}/{_topic_slug(record.topic)}/{record.id}.json"

    @staticmethod
    def _unwrap(response: httpx.Response) -> object:
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "ok":
            error = body.get("error", {})
            raise OpenVikingHTTPError(
                f"{error.get('code', 'UNKNOWN')}: {error.get('message', body)}"
            )
        return body["result"]

    async def write_knowledge(self, record: KnowledgeRecord) -> None:
        uri = self._record_uri(record)
        payload = {
            "uri": uri,
            "content": record.model_dump_json(),
            "mode": "create",
            # Deliberately not waiting for semantic/vector processing: our
            # own get_knowledge_by_id/get_relevant_knowledge only need the
            # file persisted to the tree (which happens before this call
            # returns either way), not OpenViking's VLM summarization of
            # it - waiting for that made this call time out on a local,
            # cold-start model for no benefit to us.
            "wait": False,
        }
        response = await self._client.post("/api/v1/content/write", json=payload)
        if response.status_code == 409:
            # Record already exists at this uri - update it in place instead.
            payload["mode"] = "replace"
            response = await self._client.post("/api/v1/content/write", json=payload)
        self._unwrap(response)

    async def get_knowledge_by_id(self, knowledge_id: str) -> KnowledgeRecord | None:
        glob_response = await self._client.post(
            "/api/v1/search/glob",
            json={"pattern": f"**/{knowledge_id}.json", "uri": KNOWLEDGE_ROOT},
        )
        result = self._unwrap(glob_response)
        matches = result.get("matches", [])
        if not matches:
            return None
        read_response = await self._client.get(
            "/api/v1/content/read", params={"uri": matches[0]}
        )
        raw_json = self._unwrap(read_response)
        return KnowledgeRecord.model_validate_json(raw_json)

    async def get_relevant_knowledge(self, topic: str) -> list[KnowledgeRecord]:
        # Every record for a topic lives under one directory we control
        # ourselves (see _record_uri), so an exact glob within that
        # directory is a precise topic match - no dependence on semantic
        # embedding quality, unlike a free-text `find`/`search` query.
        # `context-agent` always calls this with the exact same topic
        # string a candidate was written under, so exact matching is the
        # correct behaviour here, not a simplification.
        glob_response = await self._client.post(
            "/api/v1/search/glob",
            json={
                "pattern": "*.json",
                "uri": f"{KNOWLEDGE_ROOT}/{_topic_slug(topic)}",
            },
        )
        result = self._unwrap(glob_response)
        matches = result.get("matches", [])

        records: list[KnowledgeRecord] = []
        for uri in matches:
            read_response = await self._client.get(
                "/api/v1/content/read", params={"uri": uri}
            )
            raw_json = self._unwrap(read_response)
            records.append(KnowledgeRecord.model_validate_json(raw_json))
        return records

    async def list_conflicts(self) -> list[KnowledgeRecord]:
        raise NotImplementedError(
            "RealOpenVikingClient.list_conflicts is built in T037"
        )

    async def update_knowledge_status(
        self, knowledge_id: str, status: KnowledgeStatus
    ) -> None:
        raise NotImplementedError(
            "RealOpenVikingClient.update_knowledge_status is built in T037"
        )

    async def aclose(self) -> None:
        await self._client.aclose()

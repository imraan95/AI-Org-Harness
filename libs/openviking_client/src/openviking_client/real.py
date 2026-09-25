from __future__ import annotations

import os
import re
from datetime import datetime

import httpx

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType

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

    Implements the full `OpenVikingClient` interface: `write_knowledge`,
    `get_knowledge_by_id` (T035), `get_relevant_knowledge` (T036), and
    `list_conflicts`/`update_knowledge_status` (T037).
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

    async def _find_uri_by_id(self, knowledge_id: str) -> str | None:
        glob_response = await self._client.post(
            "/api/v1/search/glob",
            json={"pattern": f"**/{knowledge_id}.json", "uri": KNOWLEDGE_ROOT},
        )
        if glob_response.status_code == 404:
            # KNOWLEDGE_ROOT itself doesn't exist yet - nothing has ever
            # been written. Same "no matches" case as any other empty
            # glob, not an error.
            return None
        result = self._unwrap(glob_response)
        matches = result.get("matches", [])
        return matches[0] if matches else None

    async def _read_record(self, uri: str) -> KnowledgeRecord:
        read_response = await self._client.get(
            "/api/v1/content/read", params={"uri": uri}
        )
        raw_json = self._unwrap(read_response)
        return KnowledgeRecord.model_validate_json(raw_json)

    async def get_knowledge_by_id(self, knowledge_id: str) -> KnowledgeRecord | None:
        uri = await self._find_uri_by_id(knowledge_id)
        if uri is None:
            return None
        return await self._read_record(uri)

    async def get_relevant_knowledge(self, topic: str) -> list[KnowledgeRecord]:
        # Every record for a topic lives under one directory we control
        # ourselves (see _record_uri), so an exact glob within that
        # directory is a precise topic match. This intentionally does NOT
        # fall back to OpenViking's own semantic search/find - tried and
        # reverted (see docs/decisions/0008-topic-matching-via-llm-not-
        # openviking-semantic-search.md): our knowledge records are
        # written as compact JSON, and OpenViking's file-type-based
        # summarization treats `.json` as code rather than a document,
        # producing a near-identical generic "structured data record"
        # description for every single record regardless of its actual
        # topic - real testing showed this made semantic search return
        # essentially random matches, not topic-relevant ones. Bridging a
        # worded-differently topic (e.g. "Enterprise SSO" vs "SSO for
        # Enterprise Customers") is instead handled one layer up, in
        # context_agent.pipeline._retrieve, via a real LLM call
        # (llm_router's `match_topic`) reasoning over plain topic names -
        # not vector similarity over this store's file structure.
        glob_response = await self._client.post(
            "/api/v1/search/glob",
            json={
                "pattern": "*.json",
                "uri": f"{KNOWLEDGE_ROOT}/{_topic_slug(topic)}",
            },
        )
        if glob_response.status_code == 404:
            # This topic's directory doesn't exist yet - nobody has ever
            # written to it, which is the normal "brand new topic" case
            # (T041), not an error. Zero existing records, not a failure.
            return []
        result = self._unwrap(glob_response)
        matches = result.get("matches", [])
        return [await self._read_record(uri) for uri in matches]

    async def list_conflicts(self) -> list[KnowledgeRecord]:
        # grep searches file CONTENT (unlike glob, which matches paths), so
        # this finds every record with status "conflicting" regardless of
        # which topic directory it lives under - there's no server-side
        # "query by field value" endpoint, so a content-pattern search is
        # the closest real capability to that.
        grep_response = await self._client.post(
            "/api/v1/search/grep",
            json={
                "uri": KNOWLEDGE_ROOT,
                "pattern": '"status":\\s*"conflicting"',
            },
        )
        if grep_response.status_code == 404:
            # Same "nothing written yet" case as get_relevant_knowledge -
            # zero conflicts, not an error.
            return []
        result = self._unwrap(grep_response)
        # A file could in principle match on more than one line; dedupe by
        # uri while preserving order.
        seen: dict[str, None] = {}
        for match in result.get("matches", []):
            seen.setdefault(match["uri"], None)
        return [await self._read_record(uri) for uri in seen]

    async def list_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeRecord]:
        # Same "grep file content, since there's no server-side
        # query-by-field endpoint" approach as list_conflicts, matching on
        # `type` instead of `status`.
        grep_response = await self._client.post(
            "/api/v1/search/grep",
            json={
                "uri": KNOWLEDGE_ROOT,
                "pattern": f'"type":\\s*"{knowledge_type.value}"',
            },
        )
        if grep_response.status_code == 404:
            return []
        result = self._unwrap(grep_response)
        seen: dict[str, None] = {}
        for match in result.get("matches", []):
            seen.setdefault(match["uri"], None)
        return [await self._read_record(uri) for uri in seen]

    async def list_all(self) -> list[KnowledgeRecord]:
        # Same glob-then-read approach as get_relevant_knowledge, but
        # across every topic directory under the knowledge root rather
        # than one - "**/*.json" recurses.
        glob_response = await self._client.post(
            "/api/v1/search/glob",
            json={"pattern": "**/*.json", "uri": KNOWLEDGE_ROOT},
        )
        if glob_response.status_code == 404:
            return []
        result = self._unwrap(glob_response)
        matches = result.get("matches", [])
        return [await self._read_record(uri) for uri in matches]

    async def update_knowledge_status(
        self, knowledge_id: str, status: KnowledgeStatus
    ) -> None:
        uri = await self._find_uri_by_id(knowledge_id)
        if uri is None:
            # Matches FakeOpenVikingClient's behaviour: silently a no-op
            # for an unknown id, rather than raising.
            return
        record = await self._read_record(uri)
        updated = record.model_copy(update={"status": status})
        response = await self._client.post(
            "/api/v1/content/write",
            json={
                "uri": uri,
                "content": updated.model_dump_json(),
                "mode": "replace",
                "wait": False,
            },
        )
        self._unwrap(response)

    async def update_knowledge_fields(
        self, knowledge_id: str, updates: dict, edited_by: str
    ) -> None:
        # Same read-modify-write-via-replace shape as update_knowledge_status,
        # just merging arbitrary field updates instead of only `status`.
        uri = await self._find_uri_by_id(knowledge_id)
        if uri is None:
            return
        record = await self._read_record(uri)
        updated = record.model_copy(update={**updates, "edited_by": edited_by})
        response = await self._client.post(
            "/api/v1/content/write",
            json={
                "uri": uri,
                "content": updated.model_dump_json(),
                "mode": "replace",
                "wait": False,
            },
        )
        self._unwrap(response)

    async def mark_superseded(self, knowledge_id: str, superseded_at: datetime) -> None:
        # Same read-modify-write-via-replace shape as update_knowledge_status.
        uri = await self._find_uri_by_id(knowledge_id)
        if uri is None:
            return
        record = await self._read_record(uri)
        updated = record.model_copy(
            update={"status": KnowledgeStatus.SUPERSEDED, "superseded_at": superseded_at}
        )
        response = await self._client.post(
            "/api/v1/content/write",
            json={
                "uri": uri,
                "content": updated.model_dump_json(),
                "mode": "replace",
                "wait": False,
            },
        )
        self._unwrap(response)

    async def aclose(self) -> None:
        await self._client.aclose()

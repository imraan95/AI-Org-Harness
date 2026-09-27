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
# Targeted exception to ADR 0010 ("one model for every task"), for this one
# call only - a real eval run (scripts/eval_pipeline_accuracy.py) measured
# match_topic() at a 0% bridge rate on `DEFAULT_OLLAMA_MODEL`, including on
# pairs differing only in formatting. Two rounds of prompt tuning didn't fix
# it (same 2-token instant answer both times, confidently wrong in opposite
# directions) - a live comparison then showed qwen3.5:4b reasoning through
# the same pairs correctly (with visible chain-of-thought, ~15-25s/call vs.
# llama3.2's ~0.1s). Only match_topic() uses this - extract/classify/
# compare are unaffected and still share `DEFAULT_OLLAMA_MODEL`, so ADR
# 0010's simplification still holds everywhere else.
DEFAULT_OLLAMA_MATCH_TOPIC_MODEL = "qwen3.5:4b"


class OllamaLLM(LLM):
    """Calls a local Ollama server for the cheap tasks (extract, classify,
    compare).

    `generate`/`summarise` aren't wired up yet - those are decided by the
    model router (later tasks), which may send them to a different
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
        self._match_topic_model = os.environ.get(
            "OLLAMA_MATCH_TOPIC_MODEL", DEFAULT_OLLAMA_MATCH_TOPIC_MODEL
        )
        # Local model calls (especially a cold start, while Ollama loads the
        # model into memory) can take a lot longer than httpx's 5s default.
        # 300s, not 120s (see infra/README.md's Ollama contention note) -
        # OpenViking's container keeps its own models warm on the same
        # shared daemon, and confirmed real-world contention has pushed a
        # single call past 120s twice in a row (T078 manual walkthrough).
        # This is a stopgap for that contention, not a fix for it - see
        # docs/build-plan.md T078 for the real fix (a separate Ollama
        # instance dedicated to context-agent's own calls).
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url, timeout=300.0
        )

    async def _call(
        self,
        prompt: str,
        *,
        json_mode: bool = False,
        temperature: float | None = None,
        model: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self._model,
            "prompt": prompt,
            "stream": False,
        }
        if json_mode:
            # Ollama's JSON mode constrains sampling so the output is always
            # syntactically valid JSON - small models otherwise sometimes
            # produce near-JSON with a missing brace/comma.
            payload["format"] = "json"
        if temperature is not None:
            # Ollama's default sampling is stochastic (not deterministic)
            # even for the same exact prompt - fine for extract's more
            # open-ended job, but a yes/no judgment call (match_topic)
            # should give the same answer to the same question every
            # time, not vary run to run. Discovered live: the same
            # match_topic prompt answered "yes" once and "no" on a later
            # run with no other change.
            payload["options"] = {"temperature": temperature}

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
        # pipeline.py's `_compare` only calls this when `existing` is
        # non-empty (see its own "new" shortcut) - the four relationship
        # values below are exactly what docs/architecture.md's pipeline
        # step 3 and pipeline.py's `_write`/`_determine_status` match
        # against, so the model is constrained to exactly those words.
        existing_statements = "\n".join(
            f"- {record.get('statement', '')}" for record in existing
        )
        prompt = (
            "Compare this new candidate statement against the "
            "organisation's existing knowledge on the same topic. Reply "
            "with ONLY one of: new, corroborating, superseding, "
            "contradicting - meaning:\n"
            "- new: nothing existing really overlaps with this candidate\n"
            "- corroborating: this candidate agrees with and reinforces "
            "existing knowledge\n"
            "- superseding: this candidate updates or replaces existing "
            "knowledge with newer information about the same belief\n"
            "- contradicting: this candidate directly conflicts with "
            "existing knowledge\n\n"
            f"New candidate statement:\n{candidate.get('statement', '')}\n\n"
            f"Existing knowledge on this topic:\n{existing_statements}\n\n"
            "Reply with ONLY the single word, nothing else."
        )
        # temperature=0.0 for the same reason match_topic() already uses it
        # (see that method's own comment): this is a judgment call, not
        # extract()'s open-ended job, and should give the same answer to
        # the same input every time. This was missing here even though the
        # reasoning already applied - a real eval run (scripts/
        # eval_pipeline_accuracy.py) measured relationship-classification
        # accuracy at 63.6% with real confusion between contradicting/
        # superseding/corroborating, and a raw one-off comparison outside
        # the eval run got the right answer on a case the eval run got
        # wrong - consistent with unseeded sampling noise, not a
        # capability ceiling like match_topic()'s was.
        raw = await self._call(prompt, temperature=0.0)
        return raw.strip().lower()

    async def match_topic(
        self, candidate: dict[str, Any], existing_topics: list[str]
    ) -> str | None:
        # docs/decisions/0008-topic-matching-via-llm-not-openviking-
        # semantic-search.md: context_agent.pipeline._retrieve calls this
        # only when an exact-string topic lookup already came up empty -
        # it's asking "is this actually the same real-world topic as one
        # of these, just worded differently", not a first-pass search.
        # Real testing showed OpenViking's own semantic search returning
        # essentially random matches for our JSON-shaped records, so this
        # asks the model directly instead of relying on vector similarity
        # over that store's file structure.
        #
        # Asked pairwise (one yes/no question per existing topic), not as
        # a single "pick one from this list" prompt - real testing found
        # this model size answers a single yes/no reliably, but got
        # markedly less reliable (defaulting to "none" even on an obvious
        # match) once asked to choose among several options at once.
        # More calls per candidate when there are several existing
        # topics, but far more accurate at this model size - revisit if
        # the number of existing topics ever grows enough for this to be
        # too slow.
        for existing_topic in existing_topics:
            # A real eval run (scripts/eval_pipeline_accuracy.py) measured
            # this at a 0% bridge rate, including on pairs differing only
            # in formatting (e.g. "GDS connectivity" vs "gds_connectivity")
            # - the model was reading a formatting difference as a subject
            # difference. A first fix added only a positive example (same
            # subject, different formatting) - that overcorrected the other
            # way, confidently matching genuinely unrelated phrases (e.g.
            # "Mobile push notifications" vs "Enterprise SSO") that share
            # no real subject at all. This version gives both a positive
            # and a negative example side by side, so the model has both
            # signals to calibrate against instead of just one direction.
            # The negative example is deliberately unrelated to any real
            # eval-case topic, so this is a general calibration fix, not
            # something tuned to pass our own test cases.
            prompt = (
                "Do these two phrases refer to the same real-world "
                "subject, or are they different subjects that just "
                "happen to share some words or formatting? Differences "
                "in capitalization, spacing, punctuation, or style "
                "(snake_case vs. a natural phrase, abbreviations, etc.) "
                "do NOT make two phrases different - only judge the "
                "underlying subject.\n\n"
                "Examples:\n"
                "- \"Enterprise SSO\", \"enterprise_sso\", and \"SSO for "
                "Enterprise Customers\" ARE the same subject (same topic, "
                "just formatted/worded differently).\n"
                "- \"Cloud storage pricing\" and \"Cloud storage "
                "security\" are NOT the same subject (they share words, "
                "but are genuinely different topics).\n\n"
                "Reply with ONLY \"yes\" or \"no\".\n\n"
                f"Phrase 1: {candidate.get('topic', '')}\n"
                f"Phrase 2: {existing_topic}"
            )
            raw = (
                await self._call(
                    prompt, temperature=0.0, model=self._match_topic_model
                )
            ).strip().lower()
            if raw.startswith("yes"):
                return existing_topic
        return None

    async def summarise(self, text: str) -> str:
        raise NotImplementedError("OllamaLLM.summarise is not wired up yet")

    async def embed(self, text: str) -> list[float]:
        response = await self._client.post(
            "/api/embeddings",
            json={"model": self._embedding_model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]

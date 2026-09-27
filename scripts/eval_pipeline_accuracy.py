"""Runs scripts/pipeline_eval_cases.py's labeled cases through the REAL
context-agent pipeline - real Ollama (llm_router.get_llm(), per ADR 0010)
and the real Postgres knowledge store (openviking_client.get_knowledge_
store(), per ADR 0011) - and reports measured accuracy numbers, instead of
going by "the PRD's two worked examples happened to work."

Three things are measured, kept deliberately separate so a failure in one
doesn't get blamed on another:
  1. Topic-matching accuracy - did Retrieve (exact-match, then
     match_topic() per docs/decisions/0008) correctly link a candidate to
     its pre-existing belief, including the near_miss_non_match category
     nothing today measures: match_topic()'s FALSE POSITIVE rate.
  2. Relationship-classification accuracy - did Compare correctly call it
     new/corroborating/superseding/contradicting, reported as a full
     confusion matrix (which is what a real "conflict recognition"
     precision/recall number needs - not just "how often is 'contradicting'
     right", but "how often does something else get miscalled
     'contradicting'").
  3. Extraction recall ("information gain") - of a transcript's real
     content, how much actually gets surfaced as a candidate at all.

Confidence/status (ADR 0005's rules-based scoring) is deliberately NOT
scored here - it's a separate, deterministic system already unit-tested on
its own; this script is about the two LLM-accuracy questions above.

Isolation, and why it matters here specifically: this codebase already has
a documented, accepted gap (build-plan.md T065's status note) that there's
no environment separation between test runs and real data in the knowledge
store - nothing is ever deleted (architecture.md §5). Running 22 cases
through the SAME real store in one script run would otherwise let case #10
see case #3's leftover topics during its own match_topic() fallback, and
several case "families" here deliberately reuse near-identical topics
(dynamic pricing, GDS connectivity, etc.) across new/corroborating/
superseding/contradicting variants - so cross-case leakage within a single
run would silently corrupt results, not just add noise. Rather than solve
the system-wide gap, this script scopes what each case's own Retrieve step
can see to only that case's own seeded fixture, via a thin read-filtering
proxy below (_ScopedKnowledgeStore) - real reads/writes still go to the
real store underneath, so nothing about the pipeline itself is faked.

That said, RUNNING THIS SCRIPT TWICE without a fresh database still adds
real data that a future unrelated query (search_company_context, etc.)
would see - same accepted tradeoff as every existing seed/walkthrough
script. For clean, comparable numbers across repeated runs, reset local
Supabase first: `supabase db reset`.

Run with:
    uv run python scripts/eval_pipeline_accuracy.py
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from context_agent import process_transcript
from context_agent.topic_canonicalize import canonicalize_topic
from knowledge_model import KnowledgeRecord, KnowledgeStatus
from llm_router import LLM, get_llm
from openviking_client import OpenVikingClient, get_knowledge_store
from shared_schemas import Transcript

from pipeline_eval_cases import EVAL_CASES, EvalCase


class _LoggingLLM(LLM):
    """Wraps the real LLM, recording what match_topic()/compare() actually
    returned - the only way to see those decisions from outside the
    pipeline without reaching into pipeline.py's own internals.
    """

    def __init__(self, inner: LLM) -> None:
        self._inner = inner
        self.extract_calls: list[list[dict[str, Any]]] = []
        self.match_topic_calls: list[tuple[dict[str, Any], list[str], str | None]] = []
        self.compare_calls: list[tuple[dict[str, Any], list[dict[str, Any]], str]] = []

    async def generate(self, prompt: str) -> str:
        return await self._inner.generate(prompt)

    async def extract(self, text: str) -> list[dict[str, Any]]:
        result = await self._inner.extract(text)
        self.extract_calls.append(result)
        return result

    async def classify(self, text: str, categories: list[str]) -> str:
        return await self._inner.classify(text, categories)

    async def compare(
        self, candidate: dict[str, Any], existing: list[dict[str, Any]]
    ) -> str:
        result = await self._inner.compare(candidate, existing)
        self.compare_calls.append((candidate, existing, result))
        return result

    async def match_topic(
        self, candidate: dict[str, Any], existing_topics: list[str]
    ) -> str | None:
        result = await self._inner.match_topic(candidate, existing_topics)
        self.match_topic_calls.append((candidate, existing_topics, result))
        return result

    async def summarise(self, text: str) -> str:
        return await self._inner.summarise(text)

    async def embed(self, text: str) -> list[float]:
        return await self._inner.embed(text)


class _ScopedKnowledgeStore(OpenVikingClient):
    """Wraps the real knowledge store, scoping what Retrieve can see to
    just this case's own fixture(s) - see the module docstring for why.
    Writes still go to the real store; only the two read paths Retrieve
    actually uses (get_relevant_knowledge, list_all) are filtered.
    """

    def __init__(self, inner: OpenVikingClient) -> None:
        self._inner = inner
        self.visible_ids: set[str] = set()
        self.get_relevant_knowledge_calls: list[tuple[str, list[KnowledgeRecord]]] = []
        self.list_all_calls: list[list[KnowledgeRecord]] = []

    async def get_relevant_knowledge(self, topic: str) -> list[KnowledgeRecord]:
        result = await self._inner.get_relevant_knowledge(topic)
        filtered = [r for r in result if r.id in self.visible_ids]
        self.get_relevant_knowledge_calls.append((topic, filtered))
        return filtered

    async def write_knowledge(self, record: KnowledgeRecord) -> None:
        await self._inner.write_knowledge(record)
        self.visible_ids.add(record.id)

    async def get_knowledge_by_id(self, knowledge_id: str) -> KnowledgeRecord | None:
        return await self._inner.get_knowledge_by_id(knowledge_id)

    async def list_conflicts(self) -> list[KnowledgeRecord]:
        result = await self._inner.list_conflicts()
        return [r for r in result if r.id in self.visible_ids]

    async def list_by_type(self, knowledge_type) -> list[KnowledgeRecord]:
        result = await self._inner.list_by_type(knowledge_type)
        return [r for r in result if r.id in self.visible_ids]

    async def list_all(self) -> list[KnowledgeRecord]:
        result = await self._inner.list_all()
        filtered = [r for r in result if r.id in self.visible_ids]
        self.list_all_calls.append(filtered)
        return filtered

    async def update_knowledge_status(
        self, knowledge_id: str, status: KnowledgeStatus
    ) -> None:
        await self._inner.update_knowledge_status(knowledge_id, status)

    async def update_knowledge_fields(
        self, knowledge_id: str, updates: dict, edited_by: str
    ) -> None:
        await self._inner.update_knowledge_fields(knowledge_id, updates, edited_by)

    async def mark_superseded(self, knowledge_id: str, superseded_at: datetime) -> None:
        await self._inner.mark_superseded(knowledge_id, superseded_at)


async def _seed_existing(
    store: _ScopedKnowledgeStore, topic: str, statement: str
) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    record = KnowledgeRecord(
        id=f"K-eval-{uuid.uuid4()}",
        type="fact",
        topic=topic,
        statement=statement,
        status=KnowledgeStatus.ACTIVE,
        confidence=0.7,
        source_ids=["eval-fixture"],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )
    await store.write_knowledge(record)
    return record


def _reconstruct_candidates(
    candidates: list[dict[str, Any]],
    get_relevant_calls: list[tuple[str, list[KnowledgeRecord]]],
    list_all_calls: list[list[KnowledgeRecord]],
    match_topic_calls: list[tuple[dict[str, Any], list[str], str | None]],
    compare_calls: list[tuple[dict[str, Any], list[dict[str, Any]], str]],
) -> list[dict[str, Any]]:
    """Re-walks pipeline.py's own `_retrieve`/`_compare` per-candidate loop
    from the logged proxy calls, so EVERY candidate can be scored on its
    own resolved (matched_topic, relationship) - not just candidate 0.

    Why this exists (found via a real run, not assumed up front): extract()
    on a real transcript often returns several candidates - one per
    sentence/entity, not one per transcript - and the one actually on this
    case's target topic isn't reliably at index 0 (e.g. one transcript's
    candidate 0 came back with topic "Leadership", an unrelated by-product
    of the extraction, while a later candidate carried "Automated guest
    messaging templates", the one this case is actually about). Scoring
    only index 0 was silently grading the wrong candidate.

    T085 added a THIRD resolution path inside pipeline.py's `_retrieve` -
    canonicalize_topic(), a deterministic pre-filter between the exact
    match and match_topic()'s LLM fallback. It has no side effects and
    isn't logged by either proxy, so this replicates it here with the same
    inputs pipeline.py used (candidate's own topic + that candidate's
    list_all() result) rather than assuming every non-exact-match falls
    through to match_topic() - a first version of this script assumed
    exactly that, and silently scored several correctly-resolved
    candidates as complete misses once T085 shipped.

    `get_relevant_calls` and `list_all_calls` are each 1:1 with the
    candidates that reach them (pipeline.py's `_retrieve` calls
    `get_relevant_knowledge` unconditionally once per candidate, and calls
    `list_all` once per candidate whose exact match came up empty).
    `match_topic_calls` only has an entry for candidates where
    canonicalize_topic() ALSO found nothing - so both are consumed as
    queues, advanced only when a candidate actually needs them.
    `compare_calls` likewise only has an entry for candidates that ended
    up with non-empty `existing` after retrieve (pipeline.py's `_compare`
    skips the LLM call otherwise), consumed the same way.
    """
    list_all_iter = iter(list_all_calls)
    match_topic_iter = iter(match_topic_calls)
    compare_iter = iter(compare_calls)
    resolved: list[dict[str, Any]] = []
    for i, candidate in enumerate(candidates):
        matched_topic: str | None = None
        if i < len(get_relevant_calls):
            _, exact_hits = get_relevant_calls[i]
            if exact_hits:
                matched_topic = exact_hits[0].topic
            else:
                existing_records = next(list_all_iter, [])
                existing_topics = sorted({r.topic for r in existing_records})
                matched_topic = canonicalize_topic(
                    candidate.get("topic", ""), existing_topics
                )
                if matched_topic is None:
                    _, _, matched_topic = next(
                        match_topic_iter, (None, None, None)
                    )
        has_existing = matched_topic is not None
        relationship = (
            next(compare_iter, (None, None, "new"))[2] if has_existing else "new"
        )
        resolved.append(
            {
                "topic": candidate.get("topic"),
                "matched_topic": matched_topic,
                "relationship": relationship,
            }
        )
    return resolved


class CaseResult:
    def __init__(self, case: EvalCase) -> None:
        self.case = case
        self.actual_matched_topic: str | None = None
        self.actual_relationship: str | None = None
        self.keyword_recall: float = 0.0
        self.extracted_candidate_count: int = 0
        self.error: str | None = None
        # Diagnostics only - not scored, just printed so a topic-match miss
        # can be root-caused (extraction wording, wrong-candidate-index, or
        # match_topic() itself) instead of guessed at.
        self.recon: list[dict[str, Any]] = []
        self.raw_get_relevant_calls: list[tuple[str, list[Any]]] = []
        self.raw_match_topic_calls: list[tuple[dict[str, Any], list[str], str | None]] = []

    @property
    def topic_match_correct(self) -> bool:
        return self.actual_matched_topic == self.case.expected_matched_topic

    @property
    def relationship_correct(self) -> bool:
        return self.actual_relationship == self.case.expected_relationship


async def run_case(case: EvalCase) -> CaseResult:
    result = CaseResult(case)
    llm = _LoggingLLM(get_llm())
    store = _ScopedKnowledgeStore(get_knowledge_store())

    if case.existing_topic is not None:
        assert case.existing_statement is not None
        await _seed_existing(store, case.existing_topic, case.existing_statement)

    transcript = Transcript(
        id=f"eval-{case.id}-{uuid.uuid4().hex[:8]}",
        meeting_title=f"Eval case {case.id}",
        attendees=[],
        meeting_date=datetime.now(timezone.utc),
        source="eval",
        raw_text=case.transcript_text,
    )

    try:
        await process_transcript(transcript, llm, store)
    except Exception as exc:  # noqa: BLE001 - report, don't crash the run
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    if not llm.extract_calls or not llm.extract_calls[0]:
        result.error = "extract() returned no candidates"
        return result

    result.extracted_candidate_count = len(llm.extract_calls[0])

    # Keyword recall: loose, case-insensitive substring check across every
    # extracted candidate's topic+statement text - measures how much real
    # content surfaced at all, independent of which candidate is on this
    # case's specific target topic.
    haystack = " ".join(
        f"{c.get('topic', '')} {c.get('statement', '')}".lower()
        for c in llm.extract_calls[0]
    )
    if case.expected_fact_keywords:
        hits = sum(1 for kw in case.expected_fact_keywords if kw.lower() in haystack)
        result.keyword_recall = hits / len(case.expected_fact_keywords)

    result.raw_get_relevant_calls = store.get_relevant_knowledge_calls
    result.raw_match_topic_calls = llm.match_topic_calls
    result.recon = _reconstruct_candidates(
        llm.extract_calls[0],
        store.get_relevant_knowledge_calls,
        store.list_all_calls,
        llm.match_topic_calls,
        llm.compare_calls,
    )

    # Score against whichever candidate actually resolved to this case's
    # target topic - extract() often returns several candidates per
    # transcript, and the one on-topic isn't reliably at index 0 (see
    # _reconstruct_candidates's docstring).
    if case.expected_matched_topic is not None:
        hit = next(
            (c for c in result.recon if c["matched_topic"] == case.expected_matched_topic),
            None,
        )
    else:
        # "new"/near_miss cases: nothing should match - any candidate that
        # DID resolve to a real topic is a false positive worth surfacing.
        hit = next((c for c in result.recon if c["matched_topic"] is not None), None)

    if hit is not None:
        result.actual_matched_topic = hit["matched_topic"]
        result.actual_relationship = hit["relationship"]
    else:
        result.actual_matched_topic = None
        result.actual_relationship = "new"

    return result


def _print_case_line(r: CaseResult) -> None:
    c = r.case
    if r.error:
        print(f"  [ERROR] {c.id}: {r.error}")
        return
    topic_mark = "OK" if r.topic_match_correct else "MISS"
    rel_mark = "OK" if r.relationship_correct else "MISS"
    print(
        f"  [{topic_mark:>4}/{rel_mark:>4}] {c.id:<32} "
        f"topic: expected={str(c.expected_matched_topic):<24} actual={str(r.actual_matched_topic):<24} | "
        f"relationship: expected={c.expected_relationship:<13} actual={str(r.actual_relationship):<13} | "
        f"keyword_recall={r.keyword_recall:.2f}"
    )
    if not r.topic_match_correct and c.existing_topic is not None:
        print(f"        seeded_topic={c.existing_topic!r}  ({len(r.recon)} candidate(s) extracted)")
        for entry in r.recon:
            print(
                f"          candidate.topic={entry['topic']!r} -> "
                f"matched_topic={entry['matched_topic']!r}  relationship={entry['relationship']!r}"
            )
        print(f"        raw get_relevant_knowledge() calls: {r.raw_get_relevant_calls!r}")
        print(f"        raw match_topic() calls: {r.raw_match_topic_calls!r}")


async def main() -> None:
    print(f"Running {len(EVAL_CASES)} labeled eval cases against the real pipeline...\n")

    results: list[CaseResult] = []
    for i, case in enumerate(EVAL_CASES, start=1):
        # Cases were running silently for 10+ minutes with no visible
        # progress, making a genuine hang indistinguishable from a slow
        # but healthy run (qwen3.5:4b's match_topic() calls alone can take
        # ~15-25s each, and a case may need several LLM calls). Printing
        # progress per case, flushed immediately, fixes that visibility
        # gap without changing what's actually being measured.
        print(f"[{i}/{len(EVAL_CASES)}] {case.id} ...", end=" ", flush=True)
        started = time.monotonic()
        result = await run_case(case)
        elapsed = time.monotonic() - started
        status = "ERROR" if result.error else ("OK" if result.topic_match_correct and result.relationship_correct else "done")
        print(f"{status} ({elapsed:.1f}s)", flush=True)
        sys.stdout.flush()
        results.append(result)

    by_category: dict[str, list[CaseResult]] = defaultdict(list)
    for r in results:
        by_category[r.case.category].append(r)

    print("=" * 100)
    print("Per-case results")
    print("=" * 100)
    for category, group in by_category.items():
        print(f"\n-- {category} --")
        for r in group:
            _print_case_line(r)

    scored = [r for r in results if r.error is None]
    errored = [r for r in results if r.error is not None]

    print("\n" + "=" * 100)
    print("Aggregate metrics")
    print("=" * 100)
    print(f"Total cases: {len(results)}  (scored: {len(scored)}, errored: {len(errored)})")

    if scored:
        topic_acc = sum(r.topic_match_correct for r in scored) / len(scored)
        rel_acc = sum(r.relationship_correct for r in scored) / len(scored)
        avg_recall = sum(r.keyword_recall for r in scored) / len(scored)
        print(f"\nOverall topic-matching accuracy:        {topic_acc:.1%}")
        print(f"Overall relationship-classification acc: {rel_acc:.1%}")
        print(f"Overall extraction keyword recall:       {avg_recall:.1%}")

        print("\nPer-category breakdown:")
        for category, group in by_category.items():
            group_scored = [r for r in group if r.error is None]
            if not group_scored:
                print(f"  {category:<22} (no scored cases - all errored)")
                continue
            t_acc = sum(r.topic_match_correct for r in group_scored) / len(group_scored)
            r_acc = sum(r.relationship_correct for r in group_scored) / len(group_scored)
            k_rec = sum(r.keyword_recall for r in group_scored) / len(group_scored)
            print(
                f"  {category:<22} topic_acc={t_acc:.1%}  relationship_acc={r_acc:.1%}  "
                f"keyword_recall={k_rec:.1%}  (n={len(group_scored)})"
            )

        print("\nRelationship confusion matrix (rows=expected, cols=actual):")
        confusion: dict[str, Counter] = defaultdict(Counter)
        for r in scored:
            confusion[r.case.expected_relationship][str(r.actual_relationship)] += 1
        labels = ["new", "corroborating", "superseding", "contradicting"]
        header = "  " + " " * 16 + "".join(f"{lbl:>15}" for lbl in labels)
        print(header)
        for expected in labels:
            row = confusion.get(expected, Counter())
            print(f"  {expected:<16}" + "".join(f"{row.get(lbl, 0):>15}" for lbl in labels))

        print(
            "\nNear-miss non-match false-positive rate (lower is better - this is\n"
            "match_topic() incorrectly bridging two different real-world subjects):"
        )
        miss_group = [r for r in by_category.get("near_miss_non_match", []) if r.error is None]
        if miss_group:
            false_positive_rate = 1 - (
                sum(r.topic_match_correct for r in miss_group) / len(miss_group)
            )
            print(f"  {false_positive_rate:.1%}  (n={len(miss_group)})")

    if errored:
        print("\nErrored cases (excluded from metrics above):")
        for r in errored:
            print(f"  {r.case.id}: {r.error}")


if __name__ == "__main__":
    asyncio.run(main())

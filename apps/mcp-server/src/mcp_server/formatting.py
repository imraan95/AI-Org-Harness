"""T064: format a list of knowledge records as prose matching PRD §15's
structure, by user decision a deterministic template - no LLM call, so
every tool invocation is free, fast and reproducible. Trades off the
PRD example's exact flowing tone (which would need real synthesis) for
consistent, testable section structure - which is what the build-plan's
own test criterion asks for ("sections present, not exact wording").
"""

from __future__ import annotations

from typing import Any

_EMPTY_ANSWER = "Current understanding:\n\nNothing recorded on this yet.\n\nEvidence:\n(none)"


def _evidence_line(record: dict[str, Any]) -> str:
    # `sources` (real meeting title/date) is only ever present on a record
    # that came through harness-api's GET /knowledge/{id} (T058) - the
    # single-record path (get_evidence). Every other tool's records come
    # from a list endpoint that doesn't join sources, so those fall back
    # to a source count instead of a fabricated meeting name.
    sources = record.get("sources")
    if sources:
        return "\n".join(f"- {s['meeting_title']}" for s in sources)
    count = len(record.get("source_ids") or [])
    noun = "source" if count == 1 else "sources"
    return f"- {record.get('topic', 'unknown topic')}: {count} {noun}"


def format_answer(records: list[dict[str, Any]]) -> str:
    """PRD §15's shape: a "Current understanding" section, an "Evidence:"
    section, and - only when the records include a flagged conflict - a
    closing sentence naming the tension.
    """
    if not records:
        return _EMPTY_ANSWER

    understanding = "\n\n".join(r["statement"] for r in records)
    evidence = "\n".join(_evidence_line(r) for r in records)

    conflicting = [
        r for r in records if r.get("status") == "conflicting" or r.get("conflicts_with")
    ]
    tension = ""
    if conflicting:
        topics = ", ".join(sorted({r.get("topic", "unknown topic") for r in conflicting}))
        tension = (
            f"\n\nThere is currently a tension flagged in the harness: "
            f"conflicting information on {topics}."
        )

    return f"Current understanding:\n\n{understanding}\n\nEvidence:\n{evidence}{tension}"

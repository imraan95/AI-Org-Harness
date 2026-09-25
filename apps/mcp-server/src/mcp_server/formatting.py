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
    #
    # Every line ends with "(id: ...)" - without this, nothing this
    # function returns lets an agent follow up on a specific fact via
    # get_evidence/get_knowledge_history, since format_answer() is the
    # only output most tools ever produce. Discovered live: a real
    # Claude Desktop chat tried to drill into a summary answer and
    # guessed at ids (guaranteed 404s) because none were ever surfaced.
    record_id = record.get("id", "unknown id")
    sources = record.get("sources")
    if sources:
        lines = "\n".join(f"- {s['meeting_title']}" for s in sources)
        return f"{lines} (id: {record_id})"
    count = len(record.get("source_ids") or [])
    noun = "source" if count == 1 else "sources"
    return f"- {record.get('topic', 'unknown topic')}: {count} {noun} (id: {record_id})"


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


def _history_line(index: int, record: dict[str, Any]) -> str:
    status = str(record.get("status", "unknown")).upper()
    when = record.get("superseded_at") or record.get("last_updated_at") or record.get(
        "created_at"
    )
    when_str = f" ({when})" if when else ""
    return f"{index}. [{status}]{when_str} {record.get('statement', '')}"


def format_history(records: list[dict[str, Any]]) -> str:
    """T067: renders a `/knowledge/{id}/history` chain (T059) as a
    numbered, newest-to-oldest timeline.

    Deliberately NOT `format_answer()`'s merged "Current understanding"
    shape - a history view's whole point is showing which statements are
    superseded and no longer current, not blending every statement in the
    chain (old and new alike) into one summary.
    """
    if not records:
        return "No history recorded for this knowledge."
    lines = [_history_line(i, r) for i, r in enumerate(records, start=1)]
    return "History (newest to oldest):\n\n" + "\n".join(lines)

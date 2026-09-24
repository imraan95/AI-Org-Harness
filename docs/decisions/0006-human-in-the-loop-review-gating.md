# 0006 — Human-in-the-loop gating for high-impact knowledge writes

**Status:** Accepted
**Date:** 2026-09 (early planning)
**Context:** PRD §17.

## Decision

A proposed knowledge update is written with `status: pending_review` instead of `status: active` when either: it contradicts existing active knowledge, or it's low-confidence with nothing else corroborating it (`context_agent/pipeline.py::_is_high_impact`). Everything else is written as `active` immediately, with no human step.

## Why

The system writes autonomously to organisational memory based on LLM extraction from meeting transcripts — the failure mode to guard against isn't "misses something," it's "confidently states something wrong or contradictory as settled fact." Gating only the high-impact cases (not every write) keeps the human review queue small and meaningful rather than a firehose nobody reads.

## Consequence

`KnowledgeStatus.PENDING_REVIEW` records need an approve/edit/reject path (build-plan Phase 10/13: `harness-api`'s `POST /knowledge/{id}/approve|reject|edit`, surfaced in the web UI's Conflicts pane) before they're queryable as settled fact. `_is_high_impact`'s exact rule is intentionally simple for MVP (contradicting, or low-confidence-with-no-corroboration) and may need refinement once real contradictions start showing up in practice.

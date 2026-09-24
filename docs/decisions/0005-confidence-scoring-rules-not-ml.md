# 0005 — Confidence scoring is a rules/lookup table, not ML

**Status:** Accepted
**Date:** 2026-09 (early planning)
**Context:** PRD §10.

## Decision

Confidence scoring is a fixed lookup table keyed by `source_context` (e.g. `ceo_approved_decision` → high, `pm_statement`/`customer_statement` → medium, `speculation`/`casual_conversation` → low), bucketed into high/medium/low. Implemented in `context_agent/confidence.py` as a plain dict (`CONFIDENCE_BY_SOURCE_CONTEXT`) with a documented default fallback for unrecognised source contexts — not a trained model.

## Why

Confidence needs to be explainable and auditable from day one — "why was this marked high confidence" needs a one-line answer (the source context it came from), not a black-box score. A rules table is also trivial to test exhaustively (every input has a known expected output) and trivial to adjust as real usage reveals the table needs tuning, without retraining anything.

## Consequence

The table is deliberately small and coarse for MVP. If real usage shows more nuance is needed (e.g. distinguishing "PM statement in a formal planning meeting" from "PM statement in a casual hallway chat"), the fix is adding more `source_context` values, not building a model.

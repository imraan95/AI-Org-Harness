# 0009 — Postgres replaces OpenViking as the default knowledge storage layer

**Status:** Accepted (superseded in part - see update below)
**Date:** 2026-09-26
**Context:** build-plan.md's own "Open design questions — Is OpenViking still the right storage layer?", raised when 0008 removed the last thing our code asked OpenViking's semantic layer to do; forced into a real decision while scoping deployment (VPS sizing depends on whether Ollama/OpenViking need to stay hot in production).

**Update (2026-09-26):** `docs/decisions/0011-remove-openviking-entirely.md` supersedes this decision's "kept dormant... in case the decision needs to be reversed" framing. OpenViking's submodule, client, and infra have been removed entirely, not kept opt-in - the dormant path turned out to have a real, recurring cost (its container had to be manually stopped or it kept wedging Ollama, even after this decision made it non-default). This file is left below as a historical record of the original plan.

## Decision

`get_knowledge_store()` (`libs/openviking_client/src/openviking_client/router.py`) now returns a `PostgresOpenVikingClient` by default — a plain `knowledge_records` table in Supabase's Postgres, read/written via `libs/db`. Setting `KNOWLEDGE_STORE=openviking` opts back into the original `RealOpenVikingClient`. Both implement the same `OpenVikingClient` abstract interface, so `context-agent` and `harness-api` needed no changes beyond swapping which factory function they call.

OpenViking's vendored fork, its client, and its own test suite (`test_real_integration.py`) all stay in the repository, dormant rather than deleted, in case the decision needs to be reversed.

## Why

By the time this decision was made, OpenViking's actual role had already shrunk to "a smart-ish filesystem" (0008's own words): plain file storage plus `glob`/`grep` pattern matching, since 0008 moved topic-matching to a direct LLM call and nothing else in the codebase ever used OpenViking's semantic search successfully. Three concrete problems with keeping that as the *default*, not just a theoretical concern:

1. **The 256-match glob cap is real, not theoretical.** Already hit in dev (build-plan.md, "Open design questions"): `list_all()`'s underlying glob call caps at 256 matches with no pagination, so records can silently fail to appear in `search_company_context()`/`GET /context` past that count.
2. **OpenViking's own background model-keeping was a contributing cause of the Ollama contention/wedging issue** (T078). Its container keeps its own models warm on the shared default Ollama port, and T078's real fix (a second `ollama serve` instance on its own port) exists precisely because of this. Removing OpenViking as the default removes a whole source of that contention, not just a workaround for it.
3. **AGPL-3.0 licensing still has no resolved Legal sign-off in general** (`docs/research/openviking.md` §4), even though sign-off for this specific deployment has been separately confirmed by the user. Reducing what depends on it by default is the safer default for reuse of this codebase elsewhere.

Deployment sizing was the immediate trigger: a VPS that never needs to keep an LLM warm for storage lookups (SQL queries, not semantic search) is smaller and cheaper than one that does — before this decision, that sizing question couldn't be answered.

## What changed, concretely

- New `knowledge_records` table (`supabase/migrations/20260926090000_create_knowledge_records.sql`) with the same fields as the K-XXXXX JSON schema (PRD §7), as plain columns instead of one JSON file per record.
- New `PostgresOpenVikingClient` (`libs/openviking_client/src/openviking_client/postgres.py`), implementing every `OpenVikingClient` method by delegating to new `libs/db` accessor functions (`upsert_knowledge_record`, `get_knowledge_record_by_id`, `get_knowledge_records_by_topic`, `list_conflicting_knowledge_records`, `list_knowledge_records_by_type`, `list_all_knowledge_records`, `update_knowledge_record_status`, `update_knowledge_record_fields`, `mark_knowledge_record_superseded`).
- New `get_knowledge_store()` factory (`libs/openviking_client/src/openviking_client/router.py`), same "opt-in frontier, default local" shape as `llm_router.get_llm()`.
- `harness-api`'s dependency injection switched from constructing `RealOpenVikingClient()` directly to calling `get_knowledge_store()`.
- ~13 test files across `harness-api`, `mcp-server`, and `scripts/test_e2e_smoke.py` that were seeding fixtures directly into a real OpenViking instance were rewired to seed through `get_knowledge_store()` instead — otherwise they would have silently disconnected from what the app actually reads from the moment `OPENVIKING_API_KEY` was ever configured for real. See "A real design gap this surfaced" below.
- Separately (same session, independent decision — see build-plan.md's T078 "Real fix" entries and `ingestion_service/normalise.py`): `ingestion-service`'s chunk-embedding step was removed entirely, since nothing in the codebase ever read `TranscriptChunk.embedding` back for similarity search. This was ingestion-service's only remaining dependency on any LLM backend; removing it means that service no longer needs Ollama at all, independent of whether `context-agent`'s extract/classify/compare steps are ever switched off Ollama (a separate, still-paused decision — not part of this ADR).

## A real design gap this surfaced

Flipping harness-api's default broke an implicit assumption in ~13 test files: they seeded fixture data by constructing `RealOpenVikingClient()` directly, rather than through whatever harness-api actually resolves at runtime. This was silently masked in dev only because `OPENVIKING_API_KEY` isn't set in the dev shell, so those seed calls happened to hit real OpenViking while harness-api's *reads* — post-switch — went to Postgres, and the tests still passed only because none of them happened to depend on the seeded data actually being visible through the new default path in this particular run. Caught before declaring the config switch done, by running the real suite and getting explicit confirmation before doing the mechanical rewiring, rather than assuming "tests pass" meant "connected correctly."

## Consequence: pgvector zero-dimension bug found and fixed along the way

Removing the embedding step meant `TranscriptChunk.embedding` is now always `[]` rather than a real vector. `insert_transcript_chunks` was passing that empty list straight through to a `vector`-typed Postgres column, and pgvector rejects a zero-dimension vector outright (`asyncpg.exceptions.DataError: vector must have at least 1 dimension`). Fixed by storing `None` instead of `[]` when there's no embedding (`chunk.embedding or None`) — the column was already nullable and the read path already treated `NULL` as `[]`, so no schema change was needed.

## Alternatives considered

- **Keep OpenViking as the default, add pagination for the 256-match cap.** Doesn't address the Ollama-contention or AGPL considerations, and adds real engineering work (cursor-based glob pagination against an API we don't control) to keep using a layer whose only remaining job is plain storage.
- **Delete OpenViking entirely rather than keep it dormant.** Rejected — cheap to keep as a working, tested opt-in path in case the Postgres approach hits a real limitation later, and the abstract interface made keeping both trivial.

## Revisit when

If a real semantic-search need re-emerges (e.g. genuine free-text similarity search over knowledge records, not just topic-string matching — which 0008 already solved differently), Postgres has its own path there (pgvector, already enabled for `transcript_chunks`) rather than a reason to bring OpenViking back as the default.

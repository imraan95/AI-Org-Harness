# 0011 — Remove OpenViking entirely, not just make it dormant

**Status:** Accepted
**Date:** 2026-09-26
**Context:** Direct follow-up to `docs/decisions/0009-postgres-replaces-openviking-as-default-storage.md`, which made Postgres the default knowledge store but kept OpenViking's submodule, client, and infra in the tree as a dormant, opt-in alternative (`KNOWLEDGE_STORE=openviking`). Forced into a real decision the same day: a fresh terminal session hit the exact Ollama-wedging failure mode T078 already documented, root-caused to OpenViking's container still running in the background even though it was no longer the default store.

## Decision

OpenViking is removed from the codebase entirely:

- The `vendor/openviking` git submodule (properly deinitialized and removed, not just deleted from disk).
- `libs/openviking_client`'s `RealOpenVikingClient` and `OpenVikingHTTPError` (`real.py`), and its integration test (`test_real_integration.py`).
- `infra/docker-compose.yml` (OpenViking's service was the only thing in it) and `infra/openviking-config/` (its `ov.conf` and local data).
- The `KNOWLEDGE_STORE` env var branch in `openviking_client.get_knowledge_store()` - it now unconditionally returns `PostgresOpenVikingClient()`.

The abstract `OpenVikingClient` interface, `PostgresOpenVikingClient`, and `FakeOpenVikingClient` are unaffected - this decision only removes the OpenViking-backed implementation and everything that ran or vendored it. The package is still named `openviking_client` and the interface still named `OpenVikingClient` - renaming is a purely mechanical change with no behavior benefit, left as-is rather than done for its own sake.

## Why

0009 kept OpenViking dormant deliberately, as a safety net in case Postgres hit a real limitation. That safety net turned out to have a real, recurring cost that 0009 didn't fully account for: **OpenViking's container doesn't stop existing just because the app stopped defaulting to it.** It has to be manually stopped, and nothing enforces that happening - so in a fresh terminal session, the container was still running, still keeping its own models warm on the shared Ollama port, and still capable of wedging Ollama for anything else that shared that port (`ollama ps` showed `qwen3.5:4b` - OpenViking's own VLM model - stuck in `"Stopping..."`, the exact T078 signature).

T078's actual fix (a second, dedicated Ollama instance) works, but only when it's actually running and `OLLAMA_BASE_URL` is exported in the shell doing the work - neither is automatic, so a fresh session silently falls back to the contended default port. Making OpenViking dormant kept its problems dormant too, not solved: the same wedge could recur in any new terminal session, indefinitely, unless someone remembers to run `docker compose down` every time.

Weighed against that recurring, easy-to-forget cost, keeping OpenViking's code as a "cheap to reverse" safety net (0009's stated reason) had shrinking real value:

- Nothing had exercised the opt-in path since 0009 - it was reachable in principle, unverified in practice.
- The AGPL licensing question 0009 flagged as "still an outstanding general Legal item" doesn't fully go away just because the code path is dormant; removing it closes that question rather than carrying it forward indefinitely.
- Reversing this decision later, if ever needed, means re-vendoring a public git submodule and rewriting a documented ~150-line `httpx` wrapper (`docs/research/openviking.md`'s findings and this ADR's own detail are enough to redo it correctly) - real but bounded effort, not a reason to keep an actively-wedging service around indefinitely on the chance it's needed.

## What changed, concretely

- `libs/openviking_client/src/openviking_client/router.py` - `get_knowledge_store()` simplified to `return PostgresOpenVikingClient()`, kept as a one-line factory (not inlined at call sites) so a future backend swap stays a one-function change, matching `llm_router.get_llm()`'s own reasoning (docs/decisions/0010).
- `libs/openviking_client/src/openviking_client/__init__.py` - `RealOpenVikingClient`/`OpenVikingHTTPError` removed from exports.
- `libs/openviking_client/pyproject.toml` - `httpx` dropped (was only used by `real.py`).
- Deleted: `libs/openviking_client/src/openviking_client/real.py`, `libs/openviking_client/tests/test_real_integration.py`, `infra/docker-compose.yml`, `infra/openviking-config/`, the `vendor/openviking` submodule.
- `apps/context-agent/tests/test_worker.py` - its real-OpenViking e2e test (previously skipped unless `OPENVIKING_API_KEY` was set) rewritten to use `get_knowledge_store()` and run unconditionally, same pattern as every other Postgres-backed test.
- Five manual walkthrough scripts (`scripts/seed.py`, `scripts/seed_prd15_walkthrough.py`, `scripts/e2e_manual_walkthrough.py`, `scripts/e2e_walkthrough_prd_s6_belief_evolution.py`, `scripts/e2e_walkthrough_prd_s9_contradiction.py`) - swapped `RealOpenVikingClient()` for `get_knowledge_store()`, docstrings' "Requires a running OpenViking..." lines removed.
- `pyproject.toml` (workspace root) - `norecursedirs`'s comment updated (the config itself, listing `"vendor"`, is left as a harmless no-op in case anything is vendored again).
- `.gitignore` - the `infra/openviking-config/data/` entry removed.
- `infra/README.md` - rewritten; `infra/` is currently empty.

## Consequence for `docs/decisions/0009`

0009's "kept dormant... in case the decision needs to be reversed" framing is superseded by this decision. 0009 is left in place as a historical record (with a pointer added to this ADR), not rewritten.

## Risk accepted

Reversing this later costs more than flipping `KNOWLEDGE_STORE` back (0009's original design). If Postgres ever hits a real limitation - genuine semantic search at scale being the most likely candidate - re-adding OpenViking means re-vendoring the submodule and rewriting `RealOpenVikingClient` from the documentation this decision and `docs/research/openviking.md` leave behind, not a one-line config change. Accepted because: nothing had exercised that path since 0009 anyway, and a plain Postgres table with pgvector (already enabled for `transcript_chunks`) is the more likely next step for real semantic search, not OpenViking's file-store-plus-VLM-abstract approach, which 0008 already found unreliable for this data shape.

## Alternatives considered

- **Fix the "forgot to stop the container" problem instead of removing OpenViking** (e.g. a `docker compose down` step in some setup script, or a health-check that warns if it's running unexpectedly). Rejected - solves the symptom, not the underlying question of whether keeping an unused, wedging-prone service around is worth it at all, and adds its own upkeep (a script someone has to remember exists and run).
- **Keep the submodule/client but not the docker-compose service**, so at least there's no container to forget to stop. Rejected as a half-measure - the dead code (an entire vendored fork, an unused client class) still carries the AGPL question and the maintenance cost of a stale dependency, for a smaller benefit than removing it outright.

## Revisit when

If genuine semantic/similarity search over knowledge records becomes a real product need (not just topic-matching, which 0008 already solved via a direct LLM call), the first thing to try is pgvector on the `knowledge_records` table itself - already available in this Postgres instance - not re-adding OpenViking.

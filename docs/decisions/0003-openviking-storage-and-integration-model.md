# 0003 — OpenViking's storage model, and how we integrate with it

**Status:** Accepted
**Date:** 2026-09-24
**Context:** build-plan S1 research spike (`docs/research/openviking.md`) — resolving what was originally unverified about the real upstream project (ADR 0002).

## Decision

1. OpenViking has **no Postgres dependency at all** — confirmed by research, not assumed. It stores everything in its own self-contained storage engine: a virtual filesystem (`viking://...`) with a built-in vector index. This corrects earlier drafts of `architecture.md`, which assumed "Postgres + pgvector sits underneath OpenViking" and planned a separate-container hedge against sharing a Postgres instance with Supabase. That hedge was unnecessary — there was never a second Postgres to hedge against.
2. Our own Supabase Postgres + pgvector remains entirely separate infrastructure, holding what OpenViking never sees: raw transcripts, chunks, the job queue, the ingestion audit log.
3. We do **not** use OpenViking's own session/memory-extraction feature (`POST /api/v1/sessions/*`), which runs its own LLM-driven extraction/dedup pipeline into its own fixed memory taxonomy (`profile`, `preferences`, `entities`, etc.). Instead, `context-agent`'s own Extract/Compare/Classify pipeline (with PRD §10's rule-based confidence and §17's human-review gating) does all classification, and OpenViking is used purely as a semantic-searchable **file store** for the resulting `KnowledgeRecord`s — written as JSON files under `viking://resources/knowledge/{topic}/{id}.json` via `content/write`, read back via `search/glob` + `content/read` or `search/find`.

## Why

Using OpenViking's own session/memory feature would mean two competing extraction pipelines — its own LLM-driven one, and ours — each with different rules for what counts as a memory, different confidence models, and no equivalent of PRD §17's review gating. That would either duplicate work or silently bypass the rules this whole system is built around. Using it as a plain semantic file store keeps OpenViking doing what it's good at (storage + retrieval) without taking over decisions the PRD is explicit about.

## Consequence

- `libs/openviking_client`'s real implementation (`RealOpenVikingClient`) talks only to OpenViking's Resources/filesystem/search endpoints, never its Sessions endpoints.
- OpenViking's native multi-tenancy (Admin API, account/user-scoped keys) is coarser than PRD §18's eventual permissions model; our own `workspace_id`/`visibility`/etc. fields live inside the JSON payload we write, not as an OpenViking schema feature.
- **Known gap, not yet resolved:** OpenViking's Docker image tags (e.g. `v0.4.14.2`) don't cleanly track its git release tags (we vendored `v0.4.21`) — `infra/docker-compose.yml` currently runs `:latest` rather than a confirmed matching pin. Revisit before this goes beyond local dev.
- **License flag:** OpenViking's main project is AGPL-3.0. Needs RMS Legal sign-off before production — not resolved by this decision, only flagged.

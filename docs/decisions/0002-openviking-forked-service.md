# 0002 — OpenViking as a forked, separately-deployed service, part of MVP from day one

**Status:** Accepted
**Date:** 2026-09 (early planning)
**Context:** Deciding how OpenViking (PRD §12) fits into the MVP build sequence and codebase.

## Decision

OpenViking is part of the MVP from the start, not a later milestone — the Context Agent reads and writes through it from the earliest working pipeline. It is vendored as a **git submodule** (`vendor/openviking`, forked from `https://github.com/volcengine/OpenViking`, pinned to a commit/tag) and run as its **own separately deployed service**, reached only over HTTP via `libs/openviking_client`. It is not imported as a Python library.

## Why

Originally considered as a Phase-2/"later experiment" addition, then moved up: the whole point of the harness is persistent, queryable organisational memory, and building the pipeline against a throwaway in-memory fake for too long risks designing around assumptions that don't hold once a real memory/retrieval layer is involved. Running it as a separate service (not a library) keeps a clean boundary — nothing outside `vendor/openviking` touches its internals directly, and it can be upgraded, replaced, or bypassed without touching the rest of the codebase, addressing PRD §12's "the system should remain replaceable" requirement.

## Consequence

Every other service builds first against `FakeOpenVikingClient` (build-plan Phases 0–5), so the pipeline's own logic (extract/compare/classify/write, confidence rules, review gating) is fully tested before the real fork exists. The real fork only gets wired in at Phase 6 (T033+), after a dedicated research spike (S1) resolved what was originally unverified about the upstream project — see ADR 0003.

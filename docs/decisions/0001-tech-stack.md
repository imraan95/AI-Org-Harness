# 0001 — Tech stack: Next.js + Supabase + FastAPI/Python

**Status:** Accepted
**Date:** 2026-09 (early planning, before build-plan.md existed)
**Context:** Choosing a concrete stack to turn the PRD into a buildable architecture.

## Decision

- **Frontend:** Next.js (TypeScript, App Router).
- **Database + auth:** Supabase — hosted/self-hostable Postgres with pgvector already available, plus built-in auth.
- **Backend services:** Python, built on FastAPI where they expose HTTP (ingestion service, harness API, MCP server); a plain Python worker for the context agent (no HTTP surface required).

## Why

Supabase satisfies the PRD's "Postgres + pgvector" requirement directly — it isn't a new dependency layered on top, it *is* the Postgres, and it comes with auth for free rather than needing custom session/password handling. FastAPI gives auto-generated OpenAPI schemas, which is what keeps the Python backend and TypeScript frontend in sync on request/response shapes without hand-maintained duplicate types (see `scripts/generate-frontend-types.sh`).

## Consequence

This is a mixed-language monorepo: a Python `uv` workspace for the backend services/libs, and a separate Next.js project in the same repo, not a single package-manager workspace. Explained to the user in-session ("why is this monorepo and not modular") — trade-off is one repo history/PR flow for a system that's still conceptually several services, versus the coordination overhead of split repos for an MVP with one person driving all of it.

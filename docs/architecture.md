# AI Organisational Harness — Architecture Document

Companion to `prd.md`. Describes the MVP system as a buildable codebase: folder structure, component responsibilities, where state lives, and how services talk to each other.

**Stack:** Next.js (frontend) · Supabase (Postgres + pgvector + Auth) · FastAPI/Python (backend services) · OpenViking (forked, separate service).

## 1. Guiding constraints

From the PRD:

- Meetings (via Anarlog) are the only MVP source. Slack, CRM, etc. are Phase 2/3 sensors added later — the folder structure should make adding a source a matter of adding a new ingestor, not rewriting the core.
- The LLM must be swappable (open-weight by default, frontier API optional) behind a common interface.
- OpenViking is part of the MVP, not a later experiment, and it runs as its own service — forked from OpenViking's open-source repository and vendored into this codebase, not imported as a library.
- One trusted workspace, no complex RBAC — but every table carries `workspace_id`, `source_id`, `visibility`, `owner`, `access_level` so permissions can be added later without a rewrite.
- Consumption is via MCP first, REST API second, web UI third.

From this conversation's stack choice:

- **Frontend** is Next.js (TypeScript, App Router).
- **Database + auth** is Supabase — a hosted/self-hostable Postgres with pgvector already available, plus built-in auth. This satisfies the PRD's "Postgres + pgvector" requirement directly; Supabase isn't a new dependency on top of it, it *is* the Postgres.
- **Backend services** (ingestion, context agent, harness API, MCP server) are Python, built on FastAPI where they expose HTTP.
- OpenViking's own storage stays separate from Supabase (see §9) since it's a fork we don't control the schema of by default.

## 2. High-level component map

```
                        ANARLOG
                           │  (webhook / API / MCP / CLI)
                           ▼
              INGESTION SERVICE (FastAPI) ──► SUPABASE (our tables:
                           │                   transcripts, chunks, jobs)
                           ▼
                CONTEXT AGENT (Python worker)
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          Extract       Compare      Classify
              │            │            │
              └────────────┼────────────┘
                           ▼
                  openviking_client (SDK)
                           │  API calls (HTTP)
                           ▼
              ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
              │   OPENVIKING (own service)  │
              │   forked from upstream OSS   │
              │   Resources │ Memories │ Skills │
              │   own Postgres + pgvector    │
              └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
                           │
                           ▼
                 HARNESS API (FastAPI)
              ◄── Supabase Auth JWT (web users)
              ◄── static API key (service callers, e.g. MCP)
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
          MCP SERVER (Python)     NEXT.JS WEB APP
          ┌──────┼──────┐          Company Memory / Conflicts /
          ▼      ▼      ▼          Sources / Harness panes
       Claude  Cursor  Other AI    Supabase Auth login (email/
                                    magic link)
```

OpenViking is drawn with a dashed boundary because it is a separately deployed process with its own repo history (a fork we maintain), not a package that lives inside this codebase's own build.

## 3. Repository / folder structure

Python backend services share a `uv` workspace; the Next.js app is its own independent project in the same repo (mixed-language monorepo, not a single package-manager workspace).

```
org-harness/
├── apps/
│   ├── ingestion-service/       # FastAPI — receives Anarlog transcripts, normalises, queues them
│   ├── context-agent/           # Python worker — extraction/compare/classify pipeline
│   ├── harness-api/             # FastAPI — REST API over OpenViking + our own transcript store
│   ├── mcp-server/               # Python (official `mcp` SDK) — MCP tool surface for Claude/Cursor
│   └── web/                     # Next.js — the four-pane MVP UI + Supabase Auth login
│
├── vendor/
│   └── openviking/              # forked from OpenViking's open-source repo (git submodule),
│                                 # deployed and run as its own service — see §4
│
├── libs/                        # shared Python code, imported by the FastAPI/worker apps
│   ├── llm_router/              # LLM.generate/extract/classify/compare/summarise, model-agnostic
│   ├── openviking_client/       # thin SDK (httpx) that calls the OpenViking service's API
│   ├── knowledge_model/         # Pydantic KnowledgeRecord schema/enums/validation
│   ├── shared_schemas/          # Pydantic Transcript/TranscriptChunk types
│   └── db/                      # SQLAlchemy models + session for OUR Supabase tables
│
├── supabase/
│   ├── config.toml              # Supabase CLI project config (local dev)
│   └── migrations/              # SQL migrations for OUR tables only (Supabase CLI-managed)
│
├── infra/
│   ├── docker-compose.yml       # local dev: the vendored OpenViking service + its OWN
│   │                             # Postgres+pgvector (Supabase's Postgres is run separately,
│   │                             # via `supabase start`, not in this file)
│   └── env/                     # .env.example per service
│
├── docs/
│   ├── prd.md
│   ├── architecture.md          # this file
│   ├── build-plan.md
│   └── decisions/                # lightweight ADRs — first entry should record the OpenViking
│                                 # fork point and the Supabase-vs-OpenViking-storage split
│
├── pyproject.toml               # uv workspace root (members: apps/* Python services, libs/*)
│
└── scripts/
    ├── seed.py                  # load a sample transcript for local testing
    ├── replay.py                # re-run the context agent over stored transcripts
    ├── sync-openviking.sh       # pulls upstream changes into vendor/openviking, reapplies patches
    └── generate-frontend-types.sh  # runs openapi-typescript against harness-api's OpenAPI
                                     # schema, writes typed client into apps/web
```

Rationale: each `apps/*` is an independently deployable service with a single job; `vendor/openviking` is deployable too, but tracked as an upstream fork rather than written by us; `libs/*` are Python libraries with no business logic of their own beyond shared plumbing. `apps/web` is intentionally outside the `uv` workspace since it's a different language/toolchain — the two are connected only by a generated OpenAPI client, not a shared package manager.

## 4. What each part does

### supabase/ (config + migrations) and Supabase itself

Supabase is our database **and** our auth provider, not a separate thing we build:

- **Database**: a Postgres instance with pgvector enabled, holding *our own* tables (transcripts, chunks, job queue, ingestion audit log — see §5). Migrations are plain SQL files under `supabase/migrations/`, applied with the Supabase CLI (`supabase db push` / `supabase migration up`), both locally (`supabase start`, which runs Postgres + Auth + Studio in Docker under the hood) and against the hosted project.
- **Auth**: Supabase Auth issues sessions/JWTs when a user logs into the Next.js app (email/password or magic link — no custom auth code needed). Those JWTs are what `harness-api` verifies to authorize web requests (§6).

Supabase is **not** used for OpenViking's storage — see §9 for why, and the note at the end of this section.

### vendor/openviking

The OpenViking memory/context layer from PRD §12, forked from its upstream open-source repository rather than written by us:

- Brought in as a **git submodule**, pinned to a specific commit/tag, with local patches (schema extensions for `workspace_id`/`visibility`/etc., deployment config) scripted in `scripts/sync-openviking.sh` rather than edited into upstream files directly.
- Runs as its own container in `infra/docker-compose.yml`, with its own Postgres + pgvector instance — kept separate from Supabase's Postgres (see §9).
- Exposes its own API, whose exact shape depends on what the actual upstream project provides — unverified, see §9.

Nothing outside `vendor/openviking` reads or writes its database directly. All access goes through `libs/openviking_client`.

### apps/ingestion-service (FastAPI)

- `POST /webhooks/anarlog` receives new-transcript events from Anarlog (API/MCP/CLI as fallback or backfill).
- Normalises the payload into the common `Transcript`/`TranscriptChunk` shape (`libs/shared_schemas`).
- Writes the raw transcript and its chunks into **our own** Supabase tables via `libs/db`.
- Enqueues a `transcript.ingested` job (in our own `jobs` table) for the Context Agent to pick up.
- One subfolder per source (`sources/anarlog/`) so Phase 2 sources plug in alongside it without a new service.

### apps/context-agent (Python worker)

The core processing pipeline described in PRD §3, §6, §9. A polling worker (no HTTP surface required, though a thin FastAPI health endpoint is fine to add) that, for each queued transcript:

1. **Retrieve** — call `openviking_client.get_relevant_knowledge()` for the transcript's topics.
2. **Extract** — `llm_router.extract()` pulls out decisions, facts, customer insights, actions, people/ownership, candidate topics.
3. **Compare** — `llm_router.compare()` checks each candidate against retrieved knowledge: new / corroborating / superseding / contradicting.
4. **Classify** — assigns `type`, `confidence` (PRD §10 rules), `status`.
5. **Write** — `openviking_client.write_knowledge()`; high-impact changes get `status: pending_review` instead of `active` (PRD §17).

`context-agent` never opens a database connection to OpenViking's Postgres — every knowledge read/write is an HTTP call via `openviking_client`. It reads original transcript text/chunks from our own Supabase tables via `libs/db` when it needs evidence.

### apps/harness-api (FastAPI)

A REST API (PRD §14) composing two sources: OpenViking (via `openviking_client`) for knowledge, and our own Supabase tables (via `libs/db`) for evidence text. Two auth paths, since its callers aren't all human users:

- **Supabase JWT** — verified on requests from `apps/web` (a logged-in user's session token, checked against Supabase's JWT secret/JWKS).
- **Static API key** — for service-to-service callers like `apps/mcp-server`, since an MCP client (e.g. Claude Desktop) isn't a Supabase-authenticated browser session. This is a placeholder scoped to "one trusted workspace" per PRD §18, not a real multi-tenant auth model — flagged in §10 as something to revisit once permissions matter.

```
GET /context
GET /context/product
GET /context/customer
GET /context/strategy
GET /decisions
GET /people
GET /conflicts
GET /knowledge/{id}
GET /knowledge/{id}/history
POST /knowledge/{id}/approve   # human-in-the-loop actions
POST /knowledge/{id}/reject
POST /knowledge/{id}/edit
```

FastAPI's auto-generated OpenAPI schema (`/openapi.json`) is what `scripts/generate-frontend-types.sh` turns into a typed client for `apps/web` — this is the mechanism that keeps the Python backend and TypeScript frontend in sync on request/response shapes without hand-maintaining duplicate types.

### apps/mcp-server (Python, official `mcp` SDK)

Wraps the Harness API as MCP tools (PRD §14–15):

```
search_company_context()
get_current_strategy()
get_recent_decisions()
get_customer_insights()
get_product_context()
get_person_context()
get_conflicting_information()
get_evidence()
```

Each tool calls `harness-api` (using the static API key above), then formats the response with provenance (source meetings, dates, confidence) as shown in the PRD's SSO example. Runs over stdio for local Claude Desktop/Code use, or SSE if hosted remotely. Holds no state of its own.

### apps/web (Next.js)

The four-pane MVP UI from PRD §16: Company Memory, Conflicts, Sources, Harness. Two responsibilities beyond rendering:

- **Auth**: Supabase Auth (via `@supabase/ssr` or `@supabase/supabase-js`) handles login/session; unauthenticated users are redirected to a login page. This is genuinely new scope PRD didn't ask for explicitly, but it's what "Supabase for auth" implies — see §10.
- **Data**: talks only to `harness-api` (using the generated OpenAPI client, with the Supabase session's access token attached as a Bearer header) — never queries Supabase's Postgres directly. This keeps the single-query-surface principle from the earlier version of this doc intact even though Supabase would technically let the frontend query the DB directly (via Row Level Security). We deliberately don't use that path for MVP so all business logic (approve/reject rules, provenance joins) stays in one place.

### libs/openviking_client

The only piece of the codebase allowed to talk to the vendored OpenViking service. An `httpx`-based client wrapping its API behind: `get_relevant_knowledge()`, `write_knowledge()`, `get_knowledge_by_id()`, `list_conflicts()`, `update_knowledge_status()`.

### libs/llm_router

Implements the model-agnostic interface from PRD §11 as a Python abstract base class:

```python
class LLM(ABC):
    def generate(self, ...): ...
    def extract(self, ...): ...
    def classify(self, ...): ...
    def compare(self, ...): ...
    def summarise(self, ...): ...
```

Routes each call to a configured backend (Llama-family/open-weight via Ollama by default, optional frontier API) based on task complexity. This is the only place model choice is configured; no other service calls a model provider directly.

### libs/knowledge_model

Pydantic models for `KnowledgeRecord` (PRD §7) plus the `KnowledgeType`/`KnowledgeStatus` enums and the rules for status transitions and the `supersedes` chain (PRD §8) — as understood on **our** side of the API boundary (what `context-agent` builds before sending to `openviking_client`, and what `harness-api` parses OpenViking's responses into). The authoritative storage schema lives inside `vendor/openviking`, not here.

### libs/shared_schemas

Pydantic models for `Transcript` and `TranscriptChunk`, used by `ingestion-service`, `context-agent`, and `libs/db`.

### libs/db

SQLAlchemy (async, via `asyncpg`) models and session management for **our own tables only**, pointed at Supabase's Postgres connection string: `transcripts`, `transcript_chunks`, `jobs`, `ingestion_events`. Migrations are Supabase CLI SQL files, not a separate Python migration tool — `libs/db` just defines the models/queries that read and write those tables.

## 5. Where state lives

**Supabase** (our own Postgres + pgvector, `supabase/migrations/`, accessed only via `libs/db`):

| Data | Table(s) | Notes |
|---|---|---|
| Raw transcripts | `transcripts` | Full text + metadata (meeting id, attendees, date, source). Immutable once written. |
| Transcript chunks | `transcript_chunks` | Chunked text + embeddings (pgvector column), used as evidence when `harness-api` composes an answer. |
| Job queue | `jobs` | Transient — "transcript X needs processing." Not a system of record; if lost, `scripts/replay.py` rebuilds it from `transcripts`. |
| Ingestion audit log | `ingestion_events` | Record of what came in from Anarlog and when. |
| App users | Supabase's built-in `auth.users` | Managed entirely by Supabase Auth — we don't define this table ourselves. |

**OpenViking's own Postgres + pgvector** (inside `vendor/openviking`, migrated by the fork's own tooling — separate instance from Supabase):

| Data | Concept | Notes |
|---|---|---|
| Knowledge records | Memories | The K-XXXXX schema from PRD §7: id, type, topic, statement, status, confidence, source_ids, people, timestamps, `supersedes`. |
| Evidence links | Memories ↔ Resources | Points back to our `transcripts`/`transcript_chunks` row ids — cross-service reference by id, not a shared foreign key (the two Postgres instances don't know about each other). |
| People | Resources or Memories (depends on the fork's model) | Normalised person records referenced by knowledge. |
| Conflicts | Memories, flagged | Pairs of knowledge records marked contradictory, plus status (`pending`, `resolved`, `dismissed`). |
| Review queue | Memories with `status: pending_review` | High-impact proposed updates awaiting human approve/edit/reject (PRD §17). |
| Permissions scaffold | `workspace_id`, `source_id`, `visibility`, `owner`, `access_level` | Added as a local patch on top of the fork if upstream doesn't already model them — unused for enforcement in MVP but present from day one per PRD §18. |

Nothing is deleted from either store. Superseded knowledge records stay with `status: superseded` and a `supersedes`/`superseded_by` pointer (PRD §8, §20).

## 6. How services connect

```
Anarlog ──webhook──► ingestion-service ──insert (libs/db)──► Supabase (transcripts, chunks)
                             │
                          enqueue (jobs table)
                             ▼
                        context-agent (polls jobs)
                                                   │
                                     calls: llm_router (extract/compare/classify)
                                                   │
                                     calls: openviking_client ──HTTP──►
                                     OpenViking service [vendor/openviking, own Postgres]
                                                   │
harness-api ──calls openviking_client (reads knowledge)──────────┘
     │        + reads Supabase via libs/db (evidence text)
     │        + calls openviking_client (writes approve/edit/reject)
     │
     │◄── Supabase Auth JWT, from apps/web (user requests)
     │◄── static API key, from apps/mcp-server (agent requests)
     │
     ├──served to── web (Next.js; Supabase Auth for login, generated OpenAPI client for data)
     │
     └──served to── mcp-server ──tools──► Claude / Cursor / other AI agents
```

Key points:

- **OpenViking is a network dependency, not an import**, and its Postgres is never touched by anything outside `vendor/openviking`.
- **Only `context-agent` and `harness-api`'s human-review endpoints write to OpenViking**, both exclusively through `openviking_client`.
- **Only `libs/db` talks to Supabase's Postgres**, and only from `ingestion-service`, `context-agent`, and `harness-api` — never from `apps/web` directly, even though Supabase's Row Level Security would technically allow it.
- **Supabase Auth is the only auth system we build against** — no custom password handling, no session table of our own.
- **Only `libs/llm_router` talks to model providers.**
- **`mcp-server` and `web` never talk to OpenViking, Supabase, or the LLM directly.** Both go through `harness-api`, so there is exactly one query surface to secure/cache/rate-limit as the system grows past "one trusted workspace."
- **Ingestion is decoupled from processing via the `jobs` table**, so a burst of meetings (or a slow LLM/OpenViking call) doesn't block Anarlog's webhook or cause dropped transcripts.

## 7. Sequencing against the PRD's build milestones

- **M1** (transcript upload): build `context-agent` against a stubbed `openviking_client` (in-memory fake) and `FakeLLM`, fed via `scripts/seed.py` — no real OpenViking, Supabase, or Anarlog needed yet beyond a local Supabase instance for transcript storage.
- **M2** (persistent memory on OpenViking): fork OpenViking into `vendor/openviking`, stand it up in `infra/docker-compose.yml`, swap the stub for the real client.
- **M3–M4** (context comparison, contradiction detection): flesh out compare/classify against real knowledge in OpenViking.
- **M5** (Anarlog integration): build `apps/ingestion-service`, wire the webhook, confirm it writes to Supabase.
- **M6** (MCP): build `apps/harness-api` (with both auth paths) then `apps/mcp-server` on top of it.
- **M7** (temporal knowledge): `supersedes` logic, mostly in `libs/knowledge_model` + `context-agent`, surfaced through `openviking_client`.
- **M8** (first external source, post-MVP per PRD §3): new folder under `apps/ingestion-service/sources/`; no change to anything else.

## 8. What this doc deliberately leaves out

Per PRD §20: no fine-grained RBAC beyond the schema columns and the two coarse auth paths on `harness-api`, no multi-agent orchestration framework, no custom transcription, no graph database, no mobile app.

## 9. Note on the OpenViking fork itself

I don't have verified, up-to-date knowledge of OpenViking's actual open-source repository — its real API shape, storage engine, license, or how actively it's maintained. Keeping its Postgres separate from Supabase's is a deliberate hedge: if it turns out OpenViking expects to own its full Postgres instance (its own extensions, its own connection pooling assumptions), sharing Supabase's instance could conflict with how Supabase manages that database. Before building Phase 6 of `build-plan.md`, confirm: the repo URL and license, its real API transport/shape, whether it natively supports multi-tenant metadata, and whether it could in fact share a Postgres instance with Supabase safely (in which case the separate-container setup here is more caution than strictly required, and could be simplified later).

## 10. Note on the auth model

Two things here are genuinely new scope, introduced by choosing Supabase for auth rather than something the PRD asked for directly:

- The **Next.js app now has a real login screen** (Supabase Auth), where the original PRD/architecture assumed no auth at all for MVP. This seems like the right call given the stack choice, but flagging it since it's additional surface area (signup/login/session handling) beyond what PRD §16 described.
- **`harness-api`'s two auth paths** (Supabase JWT for users, a static API key for `mcp-server`) are a pragmatic MVP choice, not a real service-identity system. If more services need to call `harness-api` later, or if per-workspace permissions become real (PRD §18's future), this should be revisited — likely replaced with proper service accounts or Supabase's own service-role pattern.

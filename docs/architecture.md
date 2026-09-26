# AI Organisational Harness — Architecture Document

Companion to `prd.md`. Describes the MVP system as a buildable codebase: folder structure, component responsibilities, where state lives, and how services talk to each other.

**Stack:** Next.js (frontend) · Supabase (Postgres + pgvector + Auth) · FastAPI/Python (backend services). Knowledge storage is a plain Postgres table (`knowledge_records`, inside Supabase). OpenViking — an earlier forked, separately-deployed service that held this role from Phase 6 through `docs/decisions/0009` — has been removed entirely; see `docs/decisions/0011-remove-openviking-entirely.md`.

## 1. Guiding constraints

From the PRD:

- Meetings (via Anarlog) are the only MVP source. Slack, CRM, etc. are Phase 2/3 sensors added later — the folder structure should make adding a source a matter of adding a new ingestor, not rewriting the core.
- The LLM is reached only through a common interface, so it stays swappable even though, per ADR 0010, only one backend (Ollama, open-weight) is supported at a time today.
- Knowledge storage is reached only through the `OpenVikingClient` interface (originally built so OpenViking could be swapped for a fake in tests — the name is legacy, kept because renaming it is a mechanical change with no behavior benefit). Its only real implementation today is a plain Postgres table (ADR 0009); OpenViking itself, the interface's original namesake, has been removed from the codebase entirely (ADR 0011).
- One trusted workspace, no complex RBAC — but every table carries `workspace_id`, `source_id`, `visibility`, `owner`, `access_level` so permissions can be added later without a rewrite.
- Consumption is via MCP first, REST API second, web UI third.

From this conversation's stack choice:

- **Frontend** is Next.js (TypeScript, App Router).
- **Database + auth** is Supabase — a hosted/self-hostable Postgres with pgvector already available, plus built-in auth. This satisfies the PRD's "Postgres + pgvector" requirement directly; Supabase isn't a new dependency on top of it, it *is* the Postgres.
- **Backend services** (ingestion, context agent, harness API, MCP server) are Python, built on FastAPI where they expose HTTP.
- OpenViking (previously a separate service with its own file/vector store — see §9's history) has been removed entirely (ADR 0011); knowledge storage is Supabase's Postgres, same as everything else.

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
                  get_knowledge_store()
                           ▼
              SUPABASE knowledge_records table (plain Postgres)
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

## 3. Repository / folder structure

Python backend services share a `uv` workspace; the Next.js app is its own independent project in the same repo (mixed-language monorepo, not a single package-manager workspace).

```
org-harness/
├── apps/
│   ├── ingestion-service/       # FastAPI — receives Anarlog transcripts, normalises, queues them
│   ├── context-agent/           # Python worker — extraction/compare/classify pipeline
│   ├── harness-api/             # FastAPI — REST API over the knowledge store + transcript store
│   ├── mcp-server/               # Python (official `mcp` SDK) — MCP tool surface for Claude/Cursor
│   └── web/                     # Next.js — the four-pane MVP UI + Supabase Auth login
│
├── libs/                        # shared Python code, imported by the FastAPI/worker apps
│   ├── llm_router/              # LLM.generate/extract/classify/compare/summarise, model-agnostic
│   ├── openviking_client/       # OpenVikingClient interface (name is legacy - see ADR 0011) +
│   │                             # its one real implementation, a Postgres-backed store
│   ├── knowledge_model/         # Pydantic KnowledgeRecord schema/enums/validation
│   ├── shared_schemas/          # Pydantic Transcript/TranscriptChunk types
│   └── db/                      # SQLAlchemy models + session for OUR Supabase tables
│
├── supabase/
│   ├── config.toml              # Supabase CLI project config (local dev)
│   └── migrations/              # SQL migrations for OUR tables only (Supabase CLI-managed)
│
├── infra/                       # currently empty - see infra/README.md
│
├── docs/
│   ├── prd.md
│   ├── architecture.md          # this file
│   ├── build-plan.md
│   └── decisions/                # lightweight ADRs
│
├── pyproject.toml               # uv workspace root (members: apps/* Python services, libs/*)
│
└── scripts/
    ├── seed.py                  # load a sample transcript for local testing
    ├── replay.py                # re-run the context agent over stored transcripts
    └── generate-frontend-types.sh  # runs openapi-typescript against harness-api's OpenAPI
                                     # schema, writes typed client into apps/web
```

Rationale: each `apps/*` is an independently deployable service with a single job; `libs/*` are Python libraries with no business logic of their own beyond shared plumbing. `apps/web` is intentionally outside the `uv` workspace since it's a different language/toolchain — the two are connected only by a generated OpenAPI client, not a shared package manager. (`vendor/` and its OpenViking fork, and a `sync-openviking.sh` script, existed from Phase 6 through ADR 0011 and have been removed.)

## 4. What each part does

### supabase/ (config + migrations) and Supabase itself

Supabase is our database **and** our auth provider, not a separate thing we build:

- **Database**: a Postgres instance with pgvector enabled, holding *our own* tables (transcripts, chunks, job queue, ingestion audit log — see §5). Migrations are plain SQL files under `supabase/migrations/`, applied with the Supabase CLI (`supabase db push` / `supabase migration up`), both locally (`supabase start`, which runs Postgres + Auth + Studio in Docker under the hood) and against the hosted project.
- **Auth**: Supabase Auth issues sessions/JWTs when a user logs into the Next.js app (email/password or magic link — no custom auth code needed). Those JWTs are what `harness-api` verifies to authorize web requests (§6).

### apps/ingestion-service (FastAPI)

- `POST /webhooks/anarlog` receives new-transcript events from Anarlog (API/MCP/CLI as fallback or backfill).
- Normalises the payload into the common `Transcript`/`TranscriptChunk` shape (`libs/shared_schemas`).
- Writes the raw transcript and its chunks into **our own** Supabase tables via `libs/db`. Chunks are stored with no embedding (`transcript_chunks.embedding` is nullable, left `NULL`) — nothing in the codebase reads it back for similarity search, so computing one was pure cost; see the "Real fix" note under T078 in `build-plan.md`.
- Enqueues a `transcript.ingested` job (in our own `jobs` table) for the Context Agent to pick up.
- One subfolder per source (`sources/anarlog/`) so Phase 2 sources plug in alongside it without a new service.

### apps/context-agent (Python worker)

The core processing pipeline described in PRD §3, §6, §9. A polling worker (no HTTP surface required, though a thin FastAPI health endpoint is fine to add) that, for each queued transcript:

1. **Retrieve** — call `openviking_client.get_relevant_knowledge()` for the transcript's topics (an exact topic-string match). If that comes up empty, falls back to `llm_router.match_topic()` - asking the model directly whether any existing topic is the same real-world subject, worded differently (docs/decisions/0008).
2. **Extract** — `llm_router.extract()` pulls out decisions, facts, customer insights, actions, people/ownership, candidate topics.
3. **Compare** — `llm_router.compare()` checks each candidate against retrieved knowledge: new / corroborating / superseding / contradicting.
4. **Classify** — assigns `type`, `confidence` (PRD §10 rules), `status`.
5. **Write** — `openviking_client.write_knowledge()`; high-impact changes get `status: pending_review` instead of `active` (PRD §17).

`context-agent` never constructs a storage backend itself — every knowledge read/write goes through `openviking_client`'s abstract interface. It reads original transcript text/chunks from our own Supabase tables via `libs/db` when it needs evidence.

### apps/harness-api (FastAPI)

A REST API (PRD §14) composing two sources: the knowledge store (via `openviking_client`), and our own Supabase tables (via `libs/db`) for evidence text. Two auth paths, since its callers aren't all human users:

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

The only piece of the codebase allowed to write or read knowledge records directly. Everything else — `context-agent`, `harness-api` — calls the abstract `OpenVikingClient` interface (`get_relevant_knowledge()`, `write_knowledge()`, `get_knowledge_by_id()`, `list_conflicts()`, `list_by_type()`, `list_all()`, `update_knowledge_status()`, `update_knowledge_fields()`, `mark_superseded()`) and never knows which concrete backend answered the call. The interface and package name are a legacy of when OpenViking was the (only) implementation behind it — kept rather than renamed, since the rename itself has no behavior benefit (ADR 0011).

`get_knowledge_store()` (`router.py`) always returns:

- **`PostgresOpenVikingClient`.** Backed by a plain `knowledge_records` table (`supabase/migrations/20260926090000_create_knowledge_records.sql`, `libs/db/src/db/knowledge_records.py`). Each `OpenVikingClient` method maps directly to a `libs/db` function — `write_knowledge` → `upsert_knowledge_record` (SQLAlchemy `session.merge()`, create-or-replace by primary key), `get_relevant_knowledge`/`get_knowledge_records_by_topic` → an exact `topic ==` match, `list_conflicts`/`list_by_type`/`list_all` → filtered `SELECT`s.
- **`FakeOpenVikingClient` (tests only).** An in-memory, list-backed stand-in.

OpenViking itself (a forked, separately-deployed service this interface originally wrapped, `RealOpenVikingClient`) has been removed entirely — see ADR 0011. `get_knowledge_store()` is kept as a one-line factory rather than inlining `PostgresOpenVikingClient()` at each call site, so a different backend could be swapped in later without touching callers, same reasoning as `llm_router.get_llm()`.

### libs/llm_router

Implements the model-agnostic interface from PRD §11 as a Python abstract base class:

```python
class LLM(ABC):
    def generate(self, ...): ...
    def extract(self, ...): ...
    def classify(self, ...): ...
    def compare(self, ...): ...
    def match_topic(self, ...): ...
    def summarise(self, ...): ...
    def embed(self, ...): ...
```

`get_llm()` is the only place a concrete backend is constructed — as of `docs/decisions/0010-single-llm-backend-ollama-only.md`, it always returns `OllamaLLM()` (model configured via `OLLAMA_MODEL`, one model for every task). No frontier-API option, no per-task model tiering — both existed earlier and were removed: the tiering system in particular had never actually been wired into `OllamaLLM`, which always used a single model per instance. `context-agent`'s pipeline calls only the `LLM` interface, never `OllamaLLM` directly, so switching backends later is still a one-function change in `get_llm()`, not a pipeline rewrite. No other service calls a model provider directly.

### libs/knowledge_model

Pydantic models for `KnowledgeRecord` (PRD §7) plus the `KnowledgeType`/`KnowledgeStatus` enums and the rules for status transitions and the `supersedes` chain (PRD §8) — as understood on **our** side of the API boundary (what `context-agent` builds before sending to `openviking_client`, and what `harness-api` parses the knowledge store's responses into). The authoritative storage schema is the `knowledge_records` Postgres table (`libs/db/src/db/models.py::KnowledgeRecordRow`).

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
| Knowledge records | `knowledge_records` | The K-XXXXX schema from PRD §7 (id, type, topic, statement, status, confidence, source_ids, people, timestamps, `supersedes`, `conflicts_with`, the permissions-scaffold fields), as plain columns (see `libs/db/src/db/models.py::KnowledgeRecordRow`) — one row per record, read/written only via `PostgresOpenVikingClient`. Conflicts and the review queue aren't separate tables - they're this same table filtered by `status: conflicting` / `status: pending_review`. |

Nothing is deleted. Superseded knowledge records stay with `status: superseded` and a `supersedes`/`superseded_by` pointer (PRD §8, §20).

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
                                     calls: openviking_client (get_knowledge_store()) ──►
                                     Supabase knowledge_records table
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

- **Knowledge storage is reached only through `openviking_client`**, backed by a plain Supabase table (ADR 0009, ADR 0011).
- **Only `context-agent` and `harness-api`'s human-review endpoints write knowledge records**, both exclusively through `openviking_client`.
- **Only `libs/db` talks to Supabase's Postgres**, and only from `ingestion-service`, `context-agent`, and `harness-api` — never from `apps/web` directly, even though Supabase's Row Level Security would technically allow it.
- **Supabase Auth is the only auth system we build against** — no custom password handling, no session table of our own.
- **Only `libs/llm_router` talks to model providers.**
- **`mcp-server` and `web` never talk to the knowledge store, Supabase, or the LLM directly.** Both go through `harness-api`, so there is exactly one query surface to secure/cache/rate-limit as the system grows past "one trusted workspace."
- **Ingestion is decoupled from processing via the `jobs` table**, so a burst of meetings (or a slow LLM call) doesn't block Anarlog's webhook or cause dropped transcripts.

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

## 9. Note on the OpenViking fork itself — historical (removed entirely, ADR 0011)

**Update (2026-09-26, superseding the update below):** OpenViking has been removed from the codebase entirely - the `vendor/openviking` git submodule, `libs/openviking_client`'s `RealOpenVikingClient`, and `infra/docker-compose.yml`'s container are all gone. See `docs/decisions/0011-remove-openviking-entirely.md`. Everything below (including the first update) is kept as a historical record of the research and the decisions that followed it, not a description of anything currently in the codebase.

**Update (2026-09-26):** everything below is still an accurate record of the S1 research and the design decisions that followed it, but OpenViking is no longer the default knowledge store — see `docs/decisions/0009-postgres-replaces-openviking-as-default-storage.md`. The short version: once 0008 moved topic-matching off OpenViking's semantic search, nothing in this codebase used anything beyond plain file storage and glob/grep pattern matching — a role a plain Postgres table serves with less overhead and no outstanding AGPL question.


This used to flag OpenViking's real API shape, storage engine, and license as unverified. That research is now done — full findings in `docs/research/openviking.md`. Summary of what changed from the original assumption:

- **No Postgres, at all.** OpenViking stores everything in its own `viking://` virtual filesystem with a built-in vector index. The "keep its Postgres separate from Supabase's" hedge in earlier drafts of this doc was based on a wrong assumption — there's no second Postgres instance to hedge against. It's a genuinely separate service reached only over HTTP, which is simpler than originally planned.
- **Real API confirmed**: `POST /api/v1/content/write` (create/update a file), `POST /api/v1/search/find` (semantic search), `GET /api/v1/content/read`, plus `POST /api/v1/admin/accounts` for multi-tenant account/user management. Auth via `X-API-Key`/`Authorization: Bearer`.
- **Multi-tenancy is native, but account/user-scoped** (via the Admin API and per-key tenant resolution), not arbitrary custom metadata fields on individual records. There's an undocumented `filter` parameter on search that might support more — untested, flagged as an open item in the research doc.
- **License is AGPL-3.0** for the main project (CLI/examples are Apache 2.0). This needs sign-off from RMS Legal before production, since it wasn't evaluated by Legal as part of this research — it's an engineering finding, not a legal clearance.
- **Design decision made as a result**: we don't use OpenViking's own session/memory-extraction feature, since it runs a competing LLM pipeline into its own fixed memory taxonomy that would duplicate `context-agent`'s Extract/Compare/Classify steps and PRD §10/§17's rules. OpenViking is used purely as a semantic-searchable JSON file store for records `context-agent` has already classified — see `libs/openviking_client` in §4.

Remaining open item before Phase 6 (`build-plan.md` T033+): confirm `pip install openviking` runs cleanly on macOS without needing a local Rust/C++ toolchain (untested at time of writing), and get a real local server responding on `/health` as concrete proof it runs.

## 10. Note on the auth model

Two things here are genuinely new scope, introduced by choosing Supabase for auth rather than something the PRD asked for directly:

- The **Next.js app now has a real login screen** (Supabase Auth), where the original PRD/architecture assumed no auth at all for MVP. This seems like the right call given the stack choice, but flagging it since it's additional surface area (signup/login/session handling) beyond what PRD §16 described.
- **`harness-api`'s two auth paths** (Supabase JWT for users, a static API key for `mcp-server`) are a pragmatic MVP choice, not a real service-identity system. If more services need to call `harness-api` later, or if per-workspace permissions become real (PRD §18's future), this should be revisited — likely replaced with proper service accounts or Supabase's own service-role pattern.

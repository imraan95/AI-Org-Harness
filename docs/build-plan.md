# AI Organisational Harness — MVP Build Plan

Companion to `prd.md` and `architecture.md`. A sequential, granular task list for an engineering LLM to execute one task at a time.

**Stack:** Next.js (frontend) · Supabase (Postgres + pgvector + Auth) · FastAPI/Python (backend services) · OpenViking (forked, separate service).

## How to use this document

Give the engineering LLM **one task at a time, in order**. Each task assumes every earlier task is already done and passing. After each task:

1. The engineering LLM implements only what that task describes — nothing from later tasks.
2. It runs the task's test and reports the result.
3. You test/review it yourself.
4. If it works: commit with a message referencing the task ID (e.g. `git commit -m "T014: insert_transcript + get_transcript in libs/db"`), push to your GitHub, move to the next task.
5. If it doesn't work: send it back to the same task with what failed — don't advance.

Each task has a fixed shape: **Goal**, **Start** (what must already exist), **Do**, **Test**, and sometimes **Don't** (explicit scope guard).

Tasks marked **⚠ research needed** depend on facts about Anarlog's webhook contract or OpenViking's real upstream API that aren't verified yet (see `architecture.md` §9). Each has a **spike task** (S1, S2) that must be completed first — a spike produces a written findings doc under `docs/research/` plus one concrete proof (a running service, a real captured payload), not code. Treat a spike like any other task: one at a time, stop and review the findings doc before moving on.

---

## Phase 0 — Repo & tooling

### T001 — Scaffold the repository skeleton
**Goal:** Create the empty folder structure with no code.
**Start:** Empty repo.
**Do:** Create `apps/`, `vendor/`, `libs/`, `supabase/`, `infra/`, `docs/`, `scripts/` per `architecture.md` §3, each with a placeholder `README.md`. Add root `.gitignore` and root `README.md` linking to `docs/prd.md` and `docs/architecture.md`. Add a root `pyproject.toml` declaring a `uv` workspace with members `apps/ingestion-service`, `apps/context-agent`, `apps/harness-api`, `apps/mcp-server`, `libs/*` (empty projects for now).
**Test:** `uv sync` at the repo root completes with no errors (even with no real dependencies yet).
**Don't:** Add `apps/web` yet (T005) or any app logic.

### T002 — Supabase local dev
**Goal:** A runnable local Supabase instance (Postgres + pgvector + Auth).
**Start:** T001.
**Do:** Install the Supabase CLI, run `supabase init` at the repo root (creates `supabase/config.toml`), then `supabase start`.
**Test:** `supabase status` shows Postgres, Auth, and Studio running locally; connecting via `psql` to the local Supabase Postgres and running `SELECT * FROM pg_extension WHERE extname = 'vector';` returns a row (pgvector is pre-enabled or enabled with `CREATE EXTENSION IF NOT EXISTS vector;`).
**Don't:** Add the OpenViking container yet (T034–T035) — this task is Supabase only.

### T003 — First (empty) Supabase migration
**Goal:** Confirm the migration workflow works before writing real tables.
**Start:** T002.
**Do:** Run `supabase migration new init` to create an empty migration file under `supabase/migrations/`.
**Test:** `supabase db reset` (or `db push` against local) applies with zero errors.

### T004 — Python workspace + pytest scaffold
**Goal:** A working test command for the Python side.
**Start:** T001.
**Do:** Add `pytest` as a dev dependency at the workspace root; add one trivial passing test (`assert 1 + 1 == 2`) in `libs/knowledge_model/tests/`.
**Test:** `uv run pytest` runs and reports 1 passing test.

### T005 — Next.js scaffold
**Goal:** A running Next.js app.
**Start:** T001.
**Do:** Run `create-next-app` inside `apps/web` (TypeScript, App Router). Do not add Supabase or any data fetching yet.
**Test:** `npm run dev` inside `apps/web` starts the app; the default homepage loads in a browser.

### T006 — Frontend test runner
**Goal:** A working test command for the frontend.
**Start:** T005.
**Do:** Add Vitest + React Testing Library to `apps/web`, plus one trivial passing test.
**Test:** `npm test` inside `apps/web` runs and passes.

---

## Phase 1 — Shared types & knowledge model (Python/Pydantic)

### T007 — Knowledge record model
**Goal:** The PRD §7 knowledge record as a Pydantic model.
**Start:** T004.
**Do:** In `libs/knowledge_model`, define `KnowledgeRecord(BaseModel)`: `id, type, topic, statement, status, confidence, source_ids, people, created_at, observed_at, last_updated_at, supersedes`.
**Test:** Unit test constructs a valid instance and asserts field access; a second test omits a required field and asserts Pydantic raises `ValidationError`.

### T008 — Knowledge type & status enums
**Goal:** Fixed vocabularies for `type` and `status`.
**Start:** T007.
**Do:** Add `KnowledgeType` (`decision, fact, customer_insight, strategy, product_requirement, process, policy, person, ownership, action, hypothesis, conflict`) and `KnowledgeStatus` (`active, superseded, conflicting, pending_review, rejected`) as Python `Enum`/`StrEnum`, and use them as the field types on `KnowledgeRecord`.
**Test:** Unit test asserts the enum values exactly match this list; asserts `KnowledgeRecord(type="not_a_real_type", ...)` raises `ValidationError`.

### T009 — Transcript & TranscriptChunk models
**Goal:** Typed shapes for our own transcript store.
**Start:** T004.
**Do:** In `libs/shared_schemas`, define `Transcript` (id, meeting title, attendees, date, source, raw text) and `TranscriptChunk` (id, transcript_id, text, embedding, order) as Pydantic models.
**Test:** Unit test validates one sample object of each type; a second test with a missing field raises `ValidationError`.

---

## Phase 2 — Our own Supabase store (`libs/db`)

### T010 — `transcripts` table migration
**Goal:** Persist raw transcripts.
**Start:** T003, T009.
**Do:** `supabase migration new create_transcripts`; write SQL creating `transcripts` with columns matching the `Transcript` model.
**Test:** Apply the migration locally; query `information_schema.columns` for `transcripts` and confirm every expected column exists.

### T011 — `transcript_chunks` table migration
**Goal:** Persist chunked transcript text with embeddings.
**Start:** T010.
**Do:** `supabase migration new create_transcript_chunks`; write SQL creating `transcript_chunks` with a `vector` column for the embedding, a foreign key to `transcripts.id`, and an `order` column.
**Test:** Apply the migration; insert one dummy row with a hardcoded embedding via `psql`; select it back and confirm the vector round-trips.

### T012 — `jobs` table migration
**Goal:** A Postgres-backed job queue table.
**Start:** T010.
**Do:** `supabase migration new create_jobs`; write SQL creating `jobs` (id, type, payload jsonb, status, created_at, updated_at).
**Test:** Apply the migration; insert/select a dummy row via `psql`.

### T013 — `ingestion_events` table migration
**Goal:** An audit log of what came in from sources.
**Start:** T010.
**Do:** `supabase migration new create_ingestion_events`; write SQL creating `ingestion_events` (id, source, payload jsonb, received_at, transcript_id nullable).
**Test:** Apply the migration; insert/select a dummy row via `psql`.

### T014 — SQLAlchemy models + session
**Goal:** A Python connection to Supabase's Postgres.
**Start:** T011, T012, T013.
**Do:** In `libs/db`, set up an async SQLAlchemy engine/session pointed at the Supabase local connection string (read from env), and declare ORM models mirroring `transcripts`, `transcript_chunks`, `jobs`, `ingestion_events`.
**Test:** A unit/integration test opens a session, runs `SELECT 1`, and closes cleanly.

### T015 — `insert_transcript` / `get_transcript`
**Goal:** Basic read/write for transcripts.
**Start:** T014.
**Do:** Implement `insert_transcript(transcript)` and `get_transcript(id)` in `libs/db`.
**Test:** Integration test inserts a fixture transcript, reads it back by id, asserts field-for-field equality.

### T016 — `insert_transcript_chunks` / `get_chunks_by_transcript_id`
**Goal:** Basic read/write for chunks.
**Start:** T015.
**Do:** Implement `insert_transcript_chunks(transcript_id, chunks)` and `get_chunks_by_transcript_id(id)`.
**Test:** Integration test inserts 3 fixture chunks for one transcript, reads them back, asserts count and order.

### T017 — Job queue functions
**Goal:** Enqueue/dequeue/complete for the `jobs` table.
**Start:** T014.
**Do:** Implement `enqueue_job(type, payload)`, `dequeue_job()` (claims the oldest pending job, e.g. via `SELECT ... FOR UPDATE SKIP LOCKED`), `mark_job_done(id)`.
**Test:** Integration test enqueues one job, dequeues it (confirms a second dequeue call doesn't return it again), marks it done, confirms status via a direct query.

---

## Phase 3 — LLM router (`libs/llm_router`)

### T018 — LLM interface definition
**Goal:** The model-agnostic interface from PRD §11.
**Start:** T004.
**Do:** Define an abstract base class `LLM` with `generate()`, `extract()`, `classify()`, `compare()`, `summarise()` method signatures (typed, no implementation).
**Test:** A trivial subclass implements all methods and can be instantiated; a subclass missing one method fails to instantiate (ABC enforcement).

### T019 — `FakeLLM` test double
**Goal:** A canned-response implementation for use in every later test.
**Start:** T018.
**Do:** Implement `FakeLLM(LLM)` returning configurable fixture responses per method (e.g. `fake_llm.set_next_extract_result(...)`).
**Test:** Unit test calls each of the 5 methods and asserts it gets back the configured canned response.

### T020 — Real small-model backend (extract + classify)
**Goal:** A working call to an actual open-weight model for the cheap tasks.
**Start:** T019.
**Do:** Implement `OllamaLLM(LLM)` (or equivalent hosted small-model API) wired up for `extract()` and `classify()`, called via `httpx`.
**Test:** Integration test (skippable if no model available locally) sends a fixed short transcript snippet and asserts the response has the expected *fields* (not exact wording).

### T021 — Model router logic
**Goal:** Route each task to the configured cheapest-capable backend.
**Start:** T020.
**Do:** Add config (via `pydantic-settings`, reading env vars) mapping tasks to model tiers (e.g. `extract=small, classify=small, compare=large, summarise=small`) and a `get_model_for(task)` function.
**Test:** Unit test asserts `get_model_for("compare")` returns the configured "large" model id and is overridable via env var.

### T022 — Optional frontier-API backend
**Goal:** A pluggable frontier-model backend behind the same interface, used only if configured.
**Start:** T021.
**Do:** Add a frontier-API implementation of `LLM`, selected only when an API key is present in config; falls back to the open-weight backend otherwise.
**Test:** Unit test with no API key set asserts the router uses the open-weight backend; with a fake key set (mocked call, not a real API hit), asserts it selects the frontier backend.

---

## Phase 4 — OpenViking client interface + fake

### T023 — `openviking_client` interface definition
**Goal:** The contract every other service uses to talk to OpenViking, before OpenViking exists in the repo.
**Start:** T008.
**Do:** Define an abstract base class with `get_relevant_knowledge(topic)`, `write_knowledge(record)`, `get_knowledge_by_id(id)`, `list_conflicts()`, `update_knowledge_status(id, status)`.
**Test:** A trivial mock subclass implements and instantiates.

### T024 — `FakeOpenVikingClient`
**Goal:** An in-memory stand-in so `context-agent` can be built and tested before the real fork is wired up.
**Start:** T023.
**Do:** Implement a list-backed fake: `write_knowledge` appends, `get_knowledge_by_id` looks up by id, `get_relevant_knowledge` does a naive substring/topic match.
**Test:** Unit test writes a record, reads it back by id, and confirms a topic query returns it.

---

## Phase 5 — Context agent core pipeline (against fakes)

### T025 — `process_transcript` entrypoint stub
**Goal:** The function signature that will become the whole pipeline.
**Start:** T024, T019.
**Do:** In `apps/context-agent`, add `process_transcript(transcript)` that logs receipt and returns immediately — no real logic.
**Test:** Unit test calls it with a fixture transcript object and asserts it returns without raising.

### T026 — Extract step
**Goal:** Turn a transcript into draft knowledge candidates.
**Start:** T025.
**Do:** Implement the Extract step: call `llm.extract()` and map its output into a list of draft candidate objects.
**Test:** Unit test with `FakeLLM` configured to return a fixture extraction; asserts `extract()` was called once with the transcript's text and the function returns the expected list shape.

### T027 — Retrieve step
**Goal:** Pull existing knowledge relevant to each candidate before comparing.
**Start:** T026.
**Do:** For each candidate, call `openviking.get_relevant_knowledge(candidate.topic)`.
**Test:** Unit test seeds `FakeOpenVikingClient` with one existing record on a matching topic; asserts the retrieve step returns it for the matching candidate.

### T028 — Compare step
**Goal:** Classify the relationship between each candidate and retrieved existing knowledge.
**Start:** T027.
**Do:** Call `llm.compare(candidate, existing)`, branching on: new / corroborating / superseding / contradicting.
**Test:** Four unit tests, one per outcome, each configuring `FakeLLM` to return that outcome and asserting the pipeline branches correctly.

### T029 — Classify step (type, confidence, status)
**Goal:** Assign final `type`, `confidence`, `status` per PRD §10's rules.
**Start:** T028.
**Do:** Implement a confidence-scoring function (rules, not ML) covering the PRD §10 examples (CEO-approved decision → high, casual conversation → low, etc.), plus `llm.classify()` for the type.
**Test:** Unit tests with a few PRD §10 fixture inputs assert the correct confidence bucket (high/medium/low).

### T030 — Write step
**Goal:** Persist finished candidates to OpenViking, with human-review gating for high-impact changes.
**Start:** T029, T008.
**Do:** Call `openviking.write_knowledge()` for each candidate; if flagged high-impact (e.g. contradicts existing active knowledge, or low confidence + no corroboration), set `status: pending_review` instead of `active`.
**Test:** Unit test with one low-impact and one high-impact candidate asserts `FakeOpenVikingClient` received both with the correct statuses.

### T031 — Wire the full pipeline together
**Goal:** `process_transcript()` runs Extract → Retrieve → Compare → Classify → Write end to end.
**Start:** T030.
**Do:** Connect steps T026–T030 inside `process_transcript()`.
**Test:** One test runs a fixture transcript through the full function with `FakeLLM` + `FakeOpenVikingClient` and asserts at least one knowledge record was written with the expected `topic`/`type`.

### T032 — Seed script using the PRD's own example
**Goal:** A manually runnable demonstration of the pipeline.
**Start:** T031.
**Do:** Add `scripts/seed.py` that hardcodes the PRD §6 SSO transcript example, runs it through `process_transcript()` against the fakes, and prints the resulting knowledge record.
**Test:** Manual — run the script, confirm the printed output resembles the PRD's "Potential knowledge update" structure.

---

## Phase 6 — Fork and wire up the real OpenViking service ⚠ research needed

> Blocked on **S1** below. Do not start T033 until S1's findings doc exists and its test has passed.

### S1 — Spike: OpenViking repo research
**Goal:** Resolve every unknown flagged in `architecture.md` §9 before any other Phase 6 task starts.
**Start:** T001 (so findings have somewhere to live).
**Do:** Find and read OpenViking's actual open-source repository — check any reference docs you've been given for it first, then its own README/docs site. Write findings to `docs/research/openviking.md` covering: repo URL and license; how to run it locally (its own build/Docker instructions); its real API transport and shape (REST/gRPC/other), with one real example request/response for writing a knowledge record and one for reading it back; whether it natively supports custom multi-tenant metadata fields (this decides whether T039 is needed at all); its Postgres version/extension requirements and whether it could safely share a Postgres instance with Supabase or needs full isolation (this decides whether the separate-container setup in `architecture.md` §9 is still the right call).
**Test:** The findings doc exists and every claim in it is backed by something actually read or run (a README line, a docs page, an API response) — not inferred. As concrete proof, run the real OpenViking service locally per its own instructions and confirm it starts (health check or logs show "ready"). This running instance is what T033 onward builds on.
**Don't:** Write any `openviking_client` code yet — that starts at T035.

### T033 — Add OpenViking as a git submodule
**Goal:** Vendor the fork into the repo.
**Start:** S1 complete.
**Do:** `git submodule add` the upstream OpenViking repo at `vendor/openviking`, pinned to a specific commit/tag.
**Test:** `git submodule status` shows it checked out at the pinned commit.

### T034 — OpenViking container in docker-compose
**Goal:** A runnable local OpenViking instance, separate from Supabase.
**Start:** T033.
**Do:** Add its service (own container, own internal storage — confirmed by S1 to be a file/vector store, not Postgres) to `infra/docker-compose.yml`.
**Test:** `docker compose -f infra/docker-compose.yml up openviking` starts; `curl http://localhost:1933/health` returns `{"status": "ok", ...}`.

### T035 — Real client: `write_knowledge` + `get_knowledge_by_id`
**Goal:** First real calls against the running fork.
**Start:** T034, T023.
**Do:** Implement `OpenVikingClient` (real, `httpx`-based, not fake) for just these two methods against the fork's actual API.
**Test:** Integration test writes one record via the real client, reads it back by id from the running container, asserts equality.

### T036 — Real client: `get_relevant_knowledge`
**Goal:** Topic/similarity retrieval against the real service.
**Start:** T035.
**Do:** Implement `get_relevant_knowledge()` against the fork's real search capability.
**Test:** Integration test seeds two records on different topics; a query for one topic returns only the matching record.

### T037 — Real client: `list_conflicts` + `update_knowledge_status`
**Goal:** Complete the interface against the real service.
**Start:** T036.
**Do:** Implement the remaining two methods.
**Test:** Integration test creates two conflicting records, confirms both appear in `list_conflicts()`; calls `update_knowledge_status()` and re-reads to confirm the change persisted.

### T038 — Swap `context-agent` to the real client for dev runs
**Goal:** The pipeline now writes to a real, running OpenViking instance in dev/local runs (unit tests keep using the fake).
**Start:** T037, T032.
**Do:** Wire dependency injection so `context-agent`'s dev entrypoint uses the real `OpenVikingClient`; unit tests continue to inject `FakeOpenVikingClient`.
**Test:** Re-run `scripts/seed.py` against the real running container; confirm the knowledge record is queryable directly from OpenViking after the script runs.

### T039 — Permissions scaffold fields on `KnowledgeRecord`
**Goal:** Add `workspace_id`/`source_id`/`visibility`/`owner`/`access_level` (PRD §18) so a real permissions model can be added later without a rewrite.
**Start:** T038; resolved by S1/ADR-0003 that this is a field addition to our own model, not an OpenViking fork patch — OpenViking has no schema of its own to extend, we own the whole JSON payload.
**Do:** Add the five fields to `KnowledgeRecord` (`libs/knowledge_model`) with sensible MVP defaults (`workspace_id="default"`, `source_id="unspecified"`, `visibility="internal"`, `owner=None`, `access_level="standard"`); not enforced anywhere yet, per PRD §18's "one trusted workspace, no complex RBAC" for MVP.
**Test:** Write a record with `workspace_id` explicitly set via the real `OpenVikingClient` and confirm it round-trips through `get_knowledge_by_id`.

---

## Phase 7 — Context comparison refinement

### T040 — Similarity-based retrieval ⏸ DEFERRED (see ADR-0007)
**Goal:** Retrieve semantically related knowledge, not just exact topic string matches.
**Start:** T036 (or T027 if still on fakes).
**Do:** Update the Retrieve step to use embedding similarity with a configurable threshold.
**Test:** Integration test with two differently-worded but semantically related topics asserts both are retrieved above the threshold.
**Status:** Deferred. `docs/decisions/0007-topic-retrieval-exact-match.md` decided to ship exact-match topic retrieval (built in T036) and evaluate this only once real meeting data (post-Phase-9/Anarlog) shows topic-name drift is an actual, frequent problem rather than a theoretical one. Revisit this task then, not before.

### T041 — "No existing knowledge" path
**Goal:** Handle the first-ever mention of a topic cleanly.
**Start:** T036 (not T040 - this doesn't depend on similarity search, only on retrieval returning empty, which exact-match retrieval already does correctly).
**Do:** When retrieval returns nothing, skip Compare and classify the candidate as new with no `supersedes` link.
**Test:** Unit test with an empty retrieval result asserts the written record has `supersedes: null`.

---

## Phase 8 — Contradiction detection

### T042 — Conflict record creation
**Goal:** Contradictions produce a `conflict` record instead of silently overwriting.
**Start:** T028, T041.
**Do:** When Compare returns "contradicts," write a conflict record linking both knowledge ids with `status: pending`, instead of writing a superseding record.
**Test:** Unit test with `FakeLLM`/real LLM returning "contradicts" asserts a conflict record is created referencing both ids.

### T043 — No auto-resolution guard ⏸ DEFERRED to Phase 10 (T055/T056)
**Goal:** Guarantee the system never resolves a conflict on its own.
**Start:** T042.
**Do:** Add an explicit invariant check that no code path outside the human-review write path (T054/T055) sets a conflict's status to `resolved`/`dismissed`.
**Test:** Unit test attempts to call the internal write function with `status: resolved` from pipeline code and asserts it's rejected/raises.
**Status:** Deferred. There is no code path today that resolves a conflict at all - the only real caller of that would be `harness-api`'s approve/reject endpoints (T055/T056), which don't exist until Phase 10. Building a guard now would only be testing against code that doesn't exist yet. Build the actual guard as part of T055/T056, where the real risk lives.

---

## Phase 9 — Ingestion service + Anarlog ⚠ research needed

> Blocked on **S2** below for T045 onward. T044 itself doesn't need it (it just logs whatever arrives).

### T044 — Ingestion service scaffold + logging endpoint
**Goal:** A live HTTP endpoint that receives and logs a payload.
**Start:** T001.
**Do:** Scaffold `apps/ingestion-service` as a FastAPI app with `POST /webhooks/anarlog` that logs the raw body and returns 200. No processing yet.
**Test:** Integration test (via `httpx`/`TestClient`) POSTs a fixture payload, asserts a 200 response and that receipt was logged/captured.

### S2 — Spike: Anarlog webhook research ✅ COMPLETE
**Goal:** Resolve every unknown needed for the rest of Phase 9 before it starts.
**Status:** Done. See `docs/research/anarlog.md`: real captured `webhook.test` payload via a live ngrok tunnel to T044, full signature-verification steps, retry/idempotency behaviour, and a real gap surfaced for T046 — Anarlog has no multi-tenant concept anywhere, so per-employee identity has to be built by us (unique secret/URL per RMS user), not read off the payload. Also note: `transcript_text` in the webhook is a flat string with no speaker/timestamp structure — that data, if needed, would require the separate Pro-gated Cloud API, unconfirmed whether even that carries speaker labels.
**Start:** T044 (useful to have the endpoint to test against, but not required).
**Do:** Read Anarlog's actual API/webhook documentation — check any reference docs you've been given for it first, then Anarlog's own developer docs. Write findings to `docs/research/anarlog.md` covering: the exact webhook payload shape, including one real captured example (not a guess), showing how transcript text, speaker turns, timestamps, and meeting metadata (attendees/title/date) are represented; where/how the webhook callback URL is registered; the signature/authentication scheme used to verify a request really came from Anarlog (header name, algorithm, secret handling); any retry or rate-limit behaviour that affects how idempotent T046/T047 need to be.
**Test:** The findings doc exists, includes one real example payload, and states the exact signature verification steps in enough detail that T049 can be implemented without further guessing. As concrete proof, trigger one real (or sandbox) Anarlog webhook and confirm T044's endpoint actually receives and logs it.
**Don't:** Start T045's normaliser code yet.

### T045 — Payload normalisation ✅ COMPLETE
**Goal:** Convert Anarlog's payload shape into our `Transcript`/`TranscriptChunk` types.
**Start:** T044, T009, S2 complete.
**Do:** Implement a normaliser function (pure, no I/O) using the real Anarlog payload shape.
**Test:** Unit test feeds a fixture Anarlog payload, asserts the output matches the `Transcript`/`TranscriptChunk` models from T009.
**Status:** Done. `ingestion_service.normalise_anarlog_payload()` (pure) converts the envelope into a `Transcript` + raw chunk-text strings; `build_transcript_chunks()` (async, calls a real embedding model) turns those into `TranscriptChunk`s. Required adding `LLM.embed()` across the whole `llm_router` interface (`OllamaLLM` calls `/api/embeddings` with `qwen3-embedding:0.6b`, already pulled locally from T035; `FrontierLLM.embed` raises `NotImplementedError` - Anthropic has no embeddings API; `FakeLLM.embed` is a canned test double) - decided via explicit choice ("build real embeddings now") over stubbing, since nothing in the codebase had embedding support yet. Two open gaps carried from `docs/research/anarlog.md`, handled defensively rather than guessed at as fact: `meeting_date` falls back to the envelope's `created_at` (delivery time, not confirmed meeting time), and `participants` entries are accepted as either plain strings or objects (`name`/`display_name`). Chunk size (2000 chars, `textwrap.wrap`) is an arbitrary default - no chunking strategy exists in the PRD.

### T046 — Persist on webhook receipt ✅ COMPLETE
**Goal:** Store the normalised transcript.
**Start:** T045, T016.
**Do:** Wire the endpoint to call `insert_transcript()` + `insert_transcript_chunks()`.
**Test:** Integration test POSTs a fixture payload, then queries Supabase directly to confirm both rows exist.
**Status:** Done, with two decisions made and flagged rather than left implicit: (1) only `note.enhanced` is persisted - `meeting.completed` fires first for the same meeting and would collide on `Transcript.id` (the meeting id) if both were written, and there's no dedup/upsert task yet; `meeting.completed` and `webhook.test` are acknowledged (200) but not normalised or written. (2) Idempotency on retried deliveries (same envelope `id`) is **not** implemented - flagged in `docs/research/anarlog.md` §5 as needed before real-world use, but no task currently owns it (not T049, which is signature verification specifically). Revisit alongside T049 or add a dedicated task before this goes anywhere near production traffic.

### T047 — Enqueue processing job on webhook receipt
**Goal:** Hand off to the context agent asynchronously.
**Start:** T046, T017.
**Do:** After persisting, call `enqueue_job("transcript.ingested", {"transcript_id": ...})`.
**Test:** Integration test POSTs a fixture payload, then queries the `jobs` table and asserts one pending job references the correct transcript id.

### T048 — Context-agent worker loop
**Goal:** Actually process queued jobs.
**Start:** T047, T038.
**Do:** Add a polling loop (or a simple worker function callable on demand for tests) in `apps/context-agent` that dequeues `transcript.ingested` jobs and calls `process_transcript()` with the corresponding transcript.
**Test:** End-to-end test: POST a fixture payload to ingestion-service, run the worker once, assert a knowledge record for that content exists in OpenViking.

### T049 — Webhook signature verification
**Goal:** Reject payloads that aren't genuinely from Anarlog.
**Start:** T048; Anarlog's real auth scheme confirmed.
**Do:** Add signature/token verification per Anarlog's documented scheme.
**Test:** Integration test with a bad signature is rejected (401/403); with a valid one, proceeds as in T048.

---

## Phase 10 — Harness API

### T050 — FastAPI scaffold + `GET /knowledge/{id}` (no auth yet)
**Goal:** First read endpoint.
**Start:** T038.
**Do:** Scaffold `apps/harness-api` with this one route, calling `openviking_client.get_knowledge_by_id()`.
**Test:** Integration test seeds a record via the client, GETs it through the API, asserts the JSON matches.

### T051 — Supabase JWT auth dependency
**Goal:** Protect routes for logged-in web users.
**Start:** T050.
**Do:** Add a FastAPI dependency `get_current_user()` that verifies the `Authorization: Bearer <token>` header against Supabase's JWT secret/JWKS, and apply it to `GET /knowledge/{id}`.
**Test:** Integration test with no token gets 401; with a valid Supabase-issued token (generated via the Supabase Auth admin API in the test setup) gets 200.

### T052 — Static API key auth dependency (for service callers)
**Goal:** Let non-user services (like `mcp-server`) call the API too.
**Start:** T051.
**Do:** Add a second dependency `verify_service_key()` checking a static shared-secret header; update routes to accept *either* a valid Supabase JWT *or* a valid service key.
**Test:** Integration test with a valid service key and no user token gets 200; with neither, gets 401.

### T053 — `GET /decisions`, `GET /people`, `GET /conflicts`
**Goal:** Filtered list views.
**Start:** T052.
**Do:** Implement each as a type-filtered list over `openviking_client`, behind the same auth dependency.
**Test:** Integration test seeds fixtures of each type; each endpoint returns only its matching records.

### T054 — `GET /context`, `/context/product`, `/context/customer`, `/context/strategy`
**Goal:** Topic-scoped aggregate views.
**Start:** T053.
**Do:** Implement each as a topic-filtered view.
**Test:** Integration test seeds mixed-topic fixtures; each scoped endpoint returns only its topic's records.

### T055 — `POST /knowledge/{id}/approve`
**Goal:** Human approval flips a pending record to active.
**Start:** T052.
**Do:** Implement the route calling `update_knowledge_status(id, "active")`.
**Test:** Integration test approves a `pending_review` fixture and asserts its status becomes `active`.

### T056 — `POST /knowledge/{id}/reject`
**Goal:** Human rejection marks a record rejected (status flag, not deletion, per PRD §20).
**Start:** T055.
**Do:** Implement the route calling `update_knowledge_status(id, "rejected")`.
**Test:** Integration test rejects a fixture and asserts its status becomes `rejected`.

### T057 — `POST /knowledge/{id}/edit`
**Goal:** Human edits a proposed record before it goes active.
**Start:** T056.
**Do:** Implement the route accepting field edits, writing them, and setting `edited_by`.
**Test:** Integration test edits a fixture's `statement` field and confirms the change persists and `edited_by` is set.

### T058 — Provenance formatting
**Goal:** Every knowledge response includes readable source info, not raw ids.
**Start:** T050, T015.
**Do:** Join `source_ids` back to `transcripts` via `libs/db` and attach a `sources` array (meeting title, date) to knowledge responses.
**Test:** Integration test asserts `/knowledge/{id}` includes a `sources` array with real meeting titles/dates.

### T059 — `GET /knowledge/{id}/history`
**Goal:** Walk the `supersedes` chain.
**Start:** T058.
**Do:** Implement the endpoint, following `supersedes` backward from the given id.
**Test:** Integration test seeds a 3-link chain, calls the endpoint on the newest id, asserts all 3 come back in order.

### T060 — Generate a typed frontend client from the OpenAPI schema
**Goal:** Give `apps/web` typed access to `harness-api` without hand-written types.
**Start:** T059, T005.
**Do:** Write `scripts/generate-frontend-types.sh` running `openapi-typescript` (or `orval`) against `harness-api`'s `/openapi.json`, writing output into `apps/web`.
**Test:** Run the script against the running `harness-api`; confirm a generated `.ts` file appears with types matching the routes above.

---

## Phase 11 — MCP server

### T061 — MCP scaffold + `get_evidence`
**Goal:** First working MCP tool.
**Start:** T058, T052.
**Do:** Scaffold `apps/mcp-server` using the official Python `mcp` SDK, with one tool, `get_evidence(knowledge_id)`, calling `harness-api` with the static service key.
**Test:** Call the tool via an MCP test client; assert the result matches a direct REST call to `/knowledge/{id}` (with the service key).

### T062 — `search_company_context`, `get_recent_decisions`, `get_customer_insights`
**Goal:** Core query tools.
**Start:** T061, T054.
**Do:** Implement each, calling the corresponding `harness-api` route.
**Test:** One assertion per tool comparing MCP output to direct REST output.

### T063 — `get_current_strategy`, `get_product_context`, `get_person_context`, `get_conflicting_information`
**Goal:** Remaining tools from PRD §14.
**Start:** T062.
**Do:** Implement each.
**Test:** Same pattern as T062, one per tool.

### T064 — Provenance-formatted answers
**Goal:** Tool output reads like the PRD §15 example, not raw JSON.
**Start:** T063.
**Do:** Format each tool's response as prose with an evidence list and any flagged tension, matching PRD §15's structure.
**Test:** Snapshot test comparing output structure (sections present, not exact wording) to the PRD §15 example.

### T065 — Manual Claude walkthrough
**Goal:** Confirm the whole MCP surface works from an actual Claude client.
**Start:** T064.
**Do:** Connect `mcp-server` to Claude Desktop/Code locally (stdio config); seed fixture data reproducing the PRD §15 SSO scenario; ask "Why aren't we building SSO?"
**Test:** Manual — Claude's answer surfaces the seeded evidence, confidence, and tension, matching PRD §15's shape.

---

## Phase 12 — Temporal knowledge

### T066 — `supersedes` linking on write
**Goal:** Superseding candidates correctly link to and close out the old record.
**Start:** T028, T038.
**Do:** When Compare determines superseding, set `old.status = superseded`, `old.superseded_at = now()`, `new.supersedes = old.id`.
**Test:** Unit test runs two sequential fixture transcripts on the same topic where the second supersedes the first; asserts both records end up correctly linked/statused.

### T067 — History exposed via MCP
**Goal:** Same chain available to AI agents.
**Start:** T066, T059, T063.
**Do:** Add or extend an MCP tool to surface the `/knowledge/{id}/history` chain.
**Test:** MCP test client call returns the same chain as T059's REST call.

---

## Phase 13 — Human-in-the-loop web UI (Next.js + Supabase Auth)

### T068 — Supabase Auth login
**Goal:** Users can log in before seeing anything.
**Start:** T005.
**Do:** Add `@supabase/ssr` (or `@supabase/supabase-js`) to `apps/web`; build a login page (email/password or magic link); add middleware/layout redirecting unauthenticated users to it.
**Test:** Manual — visiting any app route while logged out redirects to login; logging in with a Supabase test user lands on the app.

### T069 — Static 4-pane shell
**Goal:** The authenticated skeleton UI with no data.
**Start:** T068.
**Do:** Add 4 nav items: Memory, Conflicts, Sources, Harness — each an empty page, only reachable when logged in.
**Test:** Manual — after logging in, all 4 links render and navigate.

### T070 — Company Memory pane
**Goal:** Show what we know/decided/changed/customers are saying.
**Start:** T069, T060, T054.
**Do:** Wire this pane to `harness-api`'s `/context/*` endpoints (via the generated client, attaching the Supabase session token), grouped per PRD §16.
**Test:** Manual — with seeded fixtures, confirm each category renders the right records.

### T071 — Conflicts pane with approve/edit/reject
**Goal:** The human-in-the-loop review surface.
**Start:** T069, T055, T056, T057.
**Do:** List pending conflicts/proposed records; wire Approve/Edit/Reject buttons to the corresponding `harness-api` routes.
**Test:** Manual — click Approve on a seeded pending record; confirm its status changes (verify via API or Supabase directly).

### T072 — Sources pane
**Goal:** Show supporting meetings for a selected knowledge item.
**Start:** T069, T058.
**Do:** Wire this pane to a knowledge item's `sources` field.
**Test:** Manual — select a seeded item; confirm the correct meeting titles/dates render.

### T073 — Harness pane
**Goal:** Show "what an AI would retrieve" for a typed topic.
**Start:** T069, T054, T062.
**Do:** Add a search box calling the same context/search path `search_company_context()` uses.
**Test:** Manual — type a seeded topic; confirm the results match what T062's MCP tool would return for the same query.

---

## Phase 14 — End-to-end verification (wrap-up)

### T074 — Automated end-to-end smoke test
**Goal:** One test exercising the full path.
**Start:** T048, T064.
**Do:** Write a single automated pytest: POST a realistic fixture transcript to `ingestion-service` → run the worker → call `search_company_context()` → assert the seeded fact is retrievable with correct provenance.
**Test:** The test itself passes.

### T075 — Manual PRD §6 walkthrough (belief evolution)
**Goal:** Confirm the system updates beliefs rather than overwriting them.
**Start:** T074.
**Do:** Feed the two PRD §6 meetings in sequence ("occasional request" then "3 enterprise customers").
**Test:** Manual — the system produces a "potential knowledge update" with both old and new context visible, per PRD §6, not a silent overwrite.

### T076 — Manual PRD §9 walkthrough (contradiction)
**Goal:** Confirm contradictions are flagged, not resolved.
**Start:** T075.
**Do:** Feed the two PRD §9 meetings ("SSO not planned for Q4" then "shipping in November").
**Test:** Manual — a conflict record appears with `status: pending`, matching PRD §9, and no automatic resolution occurs.

---

## What's intentionally not a task here

Per `architecture.md` §8 and PRD §20: no fine-grained RBAC beyond the two coarse auth paths on `harness-api`, no multi-agent framework, no custom transcription, no graph database, no mobile app, and no Phase 2/3 data sources (PRD's "first external source" milestone is post-MVP scope per PRD §3).

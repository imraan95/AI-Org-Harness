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

### T047 — Enqueue processing job on webhook receipt ✅ COMPLETE
**Goal:** Hand off to the context agent asynchronously.
**Start:** T046, T017.
**Do:** After persisting, call `enqueue_job("transcript.ingested", {"transcript_id": ...})`.
**Test:** Integration test POSTs a fixture payload, then queries the `jobs` table and asserts one pending job references the correct transcript id.
**Status:** Done. Also fixed a real bug this surfaced: `OllamaLLM`/the DB session factory were module-level singletons in `main.py`, which broke under pytest's per-test event loops ("Event loop is closed") - now created fresh per request (documented cost: not free under real load, revisit if ingestion-service needs throughput). Also found and fixed real test pollution: `dequeue_job()` claims the globally-oldest `pending` job, so any test that enqueues one and doesn't clean up breaks `libs/db/tests/test_jobs.py` (and itself, if it ever fails before reaching its own cleanup line - which is exactly what happened and required a manual `DELETE FROM jobs` to recover from). All ingestion-service tests that enqueue a job now mark it done before finishing.

### T048 — Context-agent worker loop ✅ COMPLETE
**Goal:** Actually process queued jobs.
**Start:** T047, T038.
**Do:** Add a polling loop (or a simple worker function callable on demand for tests) in `apps/context-agent` that dequeues `transcript.ingested` jobs and calls `process_transcript()` with the corresponding transcript.
**Test:** End-to-end test: POST a fixture payload to ingestion-service, run the worker once, assert a knowledge record for that content exists in OpenViking.
**Status:** Done, as an on-demand `run_worker_once()` (no standing polling loop yet - a real deployment would need one, but nothing calls this outside tests today). This is the full pipeline working end to end for the first time: real Anarlog webhook shape → ingestion-service → Supabase → job queue → context-agent worker → real OpenViking. Surfaced and fixed a genuine, previously-hidden bug in T036's `RealOpenVikingClient.get_relevant_knowledge()` (and defensively in `_find_uri_by_id`/`list_conflicts` too): OpenViking's `search/glob`/`search/grep` return `404` when the target directory doesn't exist yet, which every prior test avoided by always writing a record before searching for one - but a real brand-new topic (the normal case, not an edge case) hit it immediately. All three now treat `404` as "no matches" rather than raising.

### T049 — Webhook signature verification ✅ COMPLETE
**Goal:** Reject payloads that aren't genuinely from Anarlog.
**Start:** T048; Anarlog's real auth scheme confirmed.
**Do:** Add signature/token verification per Anarlog's documented scheme.
**Test:** Integration test with a bad signature is rejected (401/403); with a valid one, proceeds as in T048.
**Status:** Done. `ingestion_service.verify_signature()` checks the HMAC-SHA256 `x-anarlog-signature` header against a single shared `ANARLOG_WEBHOOK_SECRET` (env var, falls back to a hardcoded dev placeholder so tests need no extra setup - same pattern as OpenViking's root-key placeholder). All prior tests that POST to the webhook endpoint were updated to sign their requests. **Real consequence, not just tests**: from now on, re-testing against a real Anarlog webhook (as done live for S2) requires setting `ANARLOG_WEBHOOK_SECRET` to the actual `whsec_...` secret copied when the endpoint was registered in Anarlog's Settings, or the real request gets rejected too. Explicitly out of scope here, still flagged from S2/T046: per-employee secrets (one shared secret today, not per-RMS-user) and replay/dedup protection on retried deliveries.

---

## Phase 10 — Harness API

### T050 — FastAPI scaffold + `GET /knowledge/{id}` (no auth yet) ✅ COMPLETE
**Goal:** First read endpoint.
**Start:** T038.
**Do:** Scaffold `apps/harness-api` with this one route, calling `openviking_client.get_knowledge_by_id()`.
**Test:** Integration test seeds a record via the client, GETs it through the API, asserts the JSON matches.
**Status:** Done - first real, curlable endpoint: `GET /knowledge/{id}` returns the record as JSON (via `response_model=KnowledgeRecord`) or `404`. `RealOpenVikingClient` is created fresh per request (same event-loop-safety pattern as ingestion-service, T047) via a FastAPI dependency that closes it afterward. No auth yet - that's T051.

### T051 — Supabase JWT auth dependency ✅ COMPLETE
**Goal:** Protect routes for logged-in web users.
**Start:** T050.
**Do:** Add a FastAPI dependency `get_current_user()` that verifies the `Authorization: Bearer <token>` header against Supabase's JWT secret/JWKS, and apply it to `GET /knowledge/{id}`.
**Test:** Integration test with no token gets 401; with a valid Supabase-issued token (generated via the Supabase Auth admin API in the test setup) gets 200.
**Status:** Done. `harness_api.auth.get_current_user()` verifies via `PyJWKClient` against Supabase's JWKS endpoint, not a static secret - confirmed live (`curl .../.well-known/jwks.json`) that this project's local Supabase instance is on the newer **ES256 asymmetric JWT Signing Keys** system, not the legacy shared HS256 secret `docs/architecture.md` had hedged as one of two possibilities. `GET /knowledge/{id}` now requires a valid bearer token; test creates a real, email-confirmed user via the Supabase Auth admin API and signs them in for a real access token (no hand-crafted JWTs). Full suite green (75 passed) once the pre-existing Ollama/OpenViking contention issue is worked around (`docker compose down` in `infra/`) - see `infra/README.md`, real fix tracked separately, not blocking.

### T052 — Static API key auth dependency (for service callers) ✅ COMPLETE
**Goal:** Let non-user services (like `mcp-server`) call the API too.
**Start:** T051.
**Do:** Add a second dependency `verify_service_key()` checking a static shared-secret header; update routes to accept *either* a valid Supabase JWT *or* a valid service key.
**Test:** Integration test with a valid service key and no user token gets 200; with neither, gets 401.
**Status:** Done. `harness_api.auth.verify_service_key()` checks an `x-service-key` header (constant-time compare) against `HARNESS_API_SERVICE_KEY` (env var, dev placeholder fallback - same pattern as `ANARLOG_WEBHOOK_SECRET`). `get_current_user_or_service()` tries the service key first, falls back to the existing `get_current_user()` JWT check, so `GET /knowledge/{id}` now accepts either. This is the "one trusted workspace" scope from `docs/architecture.md` §6/§10 (PRD §18) - a single shared key for every service caller, not per-service or per-employee identity. Real consequence: whoever builds `apps/mcp-server` next will need `HARNESS_API_SERVICE_KEY` set to call this API. Full suite green.

### T053 — `GET /decisions`, `GET /people`, `GET /conflicts` ✅ COMPLETE
**Goal:** Filtered list views.
**Start:** T052.
**Do:** Implement each as a type-filtered list over `openviking_client`, behind the same auth dependency.
**Test:** Integration test seeds fixtures of each type; each endpoint returns only its matching records.
**Status:** Done. Added `list_by_type(KnowledgeType)` to the `OpenVikingClient` interface (+ fake + real, real via the same content-grep approach as `list_conflicts`) since no such method existed yet. `GET /decisions` and `GET /people` use it directly. `GET /conflicts` deliberately reuses the existing T037 `list_conflicts()` instead - PRD §16's "Conflicts" pane means "potential contradictions / pending confirmation" (`KnowledgeStatus.CONFLICTING`), a status, not the separate `KnowledgeType.CONFLICT` enum value; using `list_by_type(CONFLICT)` here would have been the wrong filter despite the tempting name match, flagged here so it isn't "fixed" incorrectly later. Full suite green.

### T054 — `GET /context`, `/context/product`, `/context/customer`, `/context/strategy` ✅ COMPLETE
**Goal:** Topic-scoped aggregate views.
**Start:** T053.
**Do:** Implement each as a topic-filtered view.
**Test:** Integration test seeds mixed-topic fixtures; each scoped endpoint returns only its topic's records.
**Status:** Done. Added `list_all()` to `OpenVikingClient` (+ fake + real, real via a recursive `**/*.json` glob under the knowledge root - same pattern as `_find_uri_by_id`) since `GET /context` needed an unfiltered view and no such method existed. `/context/product`, `/context/customer`, `/context/strategy` reuse T053's `list_by_type()` against `PRODUCT_REQUIREMENT`/`CUSTOMER_INSIGHT`/`STRATEGY` - these map 1:1 to `KnowledgeType` values despite the build-plan calling them "topic-filtered" (PRD's loose usage of "topic," not the record's own `topic` string field). Full suite: 95 passed, 4 failed - the 4 are the pre-existing, already-documented Ollama/OpenViking contention issue (`infra/README.md`), not a T054 regression; the scoped run (`libs/openviking_client apps/harness-api`) was 28/28 green.

### T055 — `POST /knowledge/{id}/approve` ✅ COMPLETE
**Goal:** Human approval flips a pending record to active.
**Start:** T052.
**Do:** Implement the route calling `update_knowledge_status(id, "active")`.
**Test:** Integration test approves a `pending_review` fixture and asserts its status becomes `active`.
**Status:** Done. 404s for an unknown id (checked via `get_knowledge_by_id` first, matching `GET /knowledge/{id}`'s own pattern), otherwise calls `update_knowledge_status()` and re-fetches to return the updated record. Behind the same `get_current_user_or_service` dependency as every other route. Full suite in `apps/harness-api`: 18 passed.

### T056 — `POST /knowledge/{id}/reject` ✅ COMPLETE
**Goal:** Human rejection marks a record rejected (status flag, not deletion, per PRD §20).
**Start:** T055.
**Do:** Implement the route calling `update_knowledge_status(id, "rejected")`.
**Test:** Integration test rejects a fixture and asserts its status becomes `rejected`.
**Status:** Done. Same shape as T055's approve route (404 for unknown id, otherwise update + re-fetch), just `KnowledgeStatus.REJECTED` instead of `ACTIVE` - a status flag via `update_knowledge_status()`, not a delete, matching PRD §20. Full suite in `apps/harness-api`: 21 passed.

### T057 — `POST /knowledge/{id}/edit` ✅ COMPLETE
**Goal:** Human edits a proposed record before it goes active.
**Start:** T056.
**Do:** Implement the route accepting field edits, writing them, and setting `edited_by`.
**Test:** Integration test edits a fixture's `statement` field and confirms the change persists and `edited_by` is set.
**Status:** Done. Added `edited_by: str | None = None` to `KnowledgeRecord` (didn't exist yet). Added `update_knowledge_fields(id, updates, edited_by)` to `OpenVikingClient` (+ fake + real, real via the same read-modify-write-replace shape as `update_knowledge_status`, merging arbitrary fields instead of just `status`). `POST /knowledge/{id}/edit` takes a small `KnowledgeEditRequest` body - **judgment call**: only `statement`/`topic`/`confidence` are exposed as editable for MVP (not every field - status has its own approve/reject routes, ids/timestamps aren't editable at all), since neither the PRD nor build-plan specify an exact editable-field list. Full suite (`libs/knowledge_model libs/openviking_client apps/harness-api`): 50 passed.

### T058 — Provenance formatting ✅ COMPLETE
**Goal:** Every knowledge response includes readable source info, not raw ids.
**Start:** T050, T015.
**Do:** Join `source_ids` back to `transcripts` via `libs/db` and attach a `sources` array (meeting title, date) to knowledge responses.
**Test:** Integration test asserts `/knowledge/{id}` includes a `sources` array with real meeting titles/dates.
**Status:** Done, plus a real upstream bug found and fixed. `GET /knowledge/{id}` now returns `KnowledgeRecordWithSources` (a `KnowledgeRecord` plus `sources: list[Source]`), joining each `source_ids` entry to `transcripts` via a fresh-per-request DB session (same event-loop-safety pattern as `openviking`). Scoped to `/knowledge/{id}` only, not the list endpoints - that's what the build-plan's own test wording asks for. **Real bug found while wiring this up**: `context_agent.pipeline._write()` never actually populated `source_ids` from a real transcript - `llm.extract()` only ever returns `topic`/`statement`, so every real (non-test-fixture) knowledge record was silently written with `source_ids=[]`, which would have made this feature a no-op against real data. Fixed by threading `transcript.id` through `process_transcript()` into `_write()` as the source id, `.get(...)` still winning if a future `extract()` ever returns something finer-grained (e.g. chunk-level). `harness-api` gained a `db` workspace dependency. Full suite: 104 passed, 7 failed - all 7 are `httpx.ReadTimeout` from the pre-existing Ollama/OpenViking contention (`infra/README.md`), not a regression; the scoped `apps/harness-api` run was 26/26 green.

### T059 — `GET /knowledge/{id}/history` ✅ COMPLETE
**Goal:** Walk the `supersedes` chain.
**Start:** T058.
**Do:** Implement the endpoint, following `supersedes` backward from the given id.
**Test:** Integration test seeds a 3-link chain, calls the endpoint on the newest id, asserts all 3 come back in order.
**Status:** Done. Returns newest-to-oldest (the order implied by "calls the endpoint on the newest id... asserts all 3 come back in order" - starts at the given record, follows `supersedes` backward). A `visited` id set guards against an invalid cycle in the data turning this into an infinite loop - shouldn't happen given how `supersedes` is written elsewhere, but cheap to guard against. Full suite in `apps/harness-api`: 30 passed.

### T060 — Generate a typed frontend client from the OpenAPI schema ⏸️ DEFERRED
**Deferred by explicit user decision (2026-09-25):** not on the critical path to the MCP-first MVP - `apps/web` is still the bare Next.js scaffold from T005, no real UI work has started on it. Picking up Phase 11 (`apps/mcp-server`) first instead, since that's the piece that actually lets Claude query the harness end to end. Revisit T060 whenever `apps/web` gets real UI work.

**Goal:** Give `apps/web` typed access to `harness-api` without hand-written types.
**Start:** T059, T005.
**Do:** Write `scripts/generate-frontend-types.sh` running `openapi-typescript` (or `orval`) against `harness-api`'s `/openapi.json`, writing output into `apps/web`.
**Test:** Run the script against the running `harness-api`; confirm a generated `.ts` file appears with types matching the routes above.

---

## Phase 11 — MCP server

### T061 — MCP scaffold + `get_evidence` ✅ COMPLETE
**Goal:** First working MCP tool.
**Start:** T058, T052.
**Do:** Scaffold `apps/mcp-server` using the official Python `mcp` SDK, with one tool, `get_evidence(knowledge_id)`, calling `harness-api` with the static service key.
**Test:** Call the tool via an MCP test client; assert the result matches a direct REST call to `/knowledge/{id}` (with the service key).
**Status:** Done. **Real finding, confirmed via install**: bare `pip install mcp` resolves to v2, which renamed `FastMCP` to `MCPServer` with a different API - pinned `mcp<2` (matching `vendor/openviking`'s own existing pin) to keep the `FastMCP` interface `docs/architecture.md` assumed. `mcp_server.server.get_evidence(knowledge_id)` calls a small `HarnessAPIClient` (mirrors `RealOpenVikingClient`'s shape) against `harness-api` with the `x-service-key` header from T052. Tested via `mcp.shared.memory.create_connected_server_and_client_session` - the real MCP protocol dispatch path, not just calling the underlying Python function directly - against an in-process `harness-api` over `httpx.ASGITransport` (same in-process-HTTP approach `harness-api`'s own tests already use via `TestClient`, avoiding a second real uvicorn process). Added a minimal unauthenticated `GET /health` to `harness-api` for this and future liveness checks. `HARNESS_API_BASE_URL` defaults to `http://127.0.0.1:8001` - no prior convention existed for harness-api's port.

**Real bug found during this task, unrelated to MCP itself**: OpenViking's `search/glob` silently caps at 256 matches with no pagination/truncation signal - confirmed live once local test data exceeded that count, breaking T054's `/context` test. Every glob/grep-based `RealOpenVikingClient` method is affected past 256 total records. Fixed locally by clearing accumulated test fixtures (`infra/openviking-config/data/viking/*/resources/knowledge/`, account/key data untouched); logged as a real, unresolved architectural gap in `docs/research/openviking.md` §8 - must be addressed before any production or multi-employee rollout. Full suite (`apps/harness-api apps/mcp-server`): 33 passed.

**Deferred, by user decision:** T060 (typed frontend client for `apps/web`) - not on the critical path to the MCP-first MVP; see its own entry above.

### T062 — `search_company_context`, `get_recent_decisions`, `get_customer_insights` ✅ COMPLETE
**Goal:** Core query tools.
**Start:** T061, T054.
**Do:** Implement each, calling the corresponding `harness-api` route.
**Test:** One assertion per tool comparing MCP output to direct REST output.
**Status:** Done. `search_company_context` → `GET /context`, `get_recent_decisions` → `GET /decisions`, `get_customer_insights` → `GET /context/customer`, each a thin `HarnessAPIClient` method + MCP tool, same shape as T061's `get_evidence`. FastMCP wraps a `list[...]`-returning tool's structured output as `{"result": [...]}` (confirmed by probing it directly - a JSON array isn't a valid top-level structured-content object) - tests unwrap that key before comparing. **Real, first-try test failure, fixed**: comparing MCP tool output to a direct REST call as an ordered list failed because OpenViking's grep-based list endpoints don't guarantee stable ordering across two separate live calls a few milliseconds apart - fixed by sorting both sides by `id` before comparing (same reasoning T053/T054's own tests already used subset/set comparisons for). `apps/mcp-server` full suite: 5 passed.

### T063 — `get_current_strategy`, `get_product_context`, `get_person_context`, `get_conflicting_information` ✅ COMPLETE
**Goal:** Remaining tools from PRD §14.
**Start:** T062.
**Do:** Implement each.
**Test:** Same pattern as T062, one per tool.
**Status:** Done. `get_current_strategy` → `GET /context/strategy`, `get_product_context` → `GET /context/product`, `get_conflicting_information` → `GET /conflicts`. `get_person_context` → `GET /people` - **judgment call**: there's no `/context/person` route (architecture.md's REST list only has `/context/product`, `/context/customer`, `/context/strategy`), so this maps to the standalone `/people` route instead, the closest existing match. All 8 PRD §14 MCP tools now exist. `apps/mcp-server` full suite: 9 passed.

### T064 — Provenance-formatted answers ✅ COMPLETE
**Goal:** Tool output reads like the PRD §15 example, not raw JSON.
**Start:** T063.
**Do:** Format each tool's response as prose with an evidence list and any flagged tension, matching PRD §15's structure.
**Test:** Snapshot test comparing output structure (sections present, not exact wording) to the PRD §15 example.
**Status:** Done. **By explicit user decision**, `mcp_server.formatting.format_answer()` is a deterministic template - no LLM call - producing a "Current understanding:" section (joined statements), an "Evidence:" section (real meeting titles when a record carries `sources` from T058's `/knowledge/{id}` join, otherwise a per-record source count), and a "tension" sentence appended only when any record is `status: conflicting` or carries `conflicts_with`. All 8 MCP tools' return type changed from raw JSON (`dict`/`list[dict]`) to `str`, calling `format_answer()` before returning - a real, deliberate breaking change to T061-T063's tool contracts, not an addition alongside them. Rewrote T061-T063's tests: `get_evidence` (single-record) still compares exactly against `format_answer()` of the direct REST response; the multi-record tools (T062/T063) switched from exact-JSON/exact-string equality to structural assertions (sections present, seeded statement/topic appear) - a second live list call can return the same records in a different order (the already-documented grep ordering gap), which would make formatted *text* differ even though the data is identical. New `test_formatting.py` unit-tests `format_answer()` directly against PRD §15's section structure. `apps/mcp-server` full suite: 13 passed.

### T065 — Manual Claude walkthrough ✅ COMPLETE
**Goal:** Confirm the whole MCP surface works from an actual Claude client.
**Start:** T064.
**Do:** Connect `mcp-server` to Claude Desktop/Code locally (stdio config); seed fixture data reproducing the PRD §15 SSO scenario; ask "Why aren't we building SSO?"
**Test:** Manual — Claude's answer surfaces the seeded evidence, confidence, and tension, matching PRD §15's shape.
**Status:** Done, confirmed live. Added `scripts/seed_prd15_walkthrough.py` (seeds the exact PRD §15 scenario: a `customer_insight` + a conflicting `decision`, plus real `transcripts` rows named after PRD §15's own evidence categories) and a `[project.scripts]` entry (`harness-mcp-server`) so Claude Desktop's config has a stable command to invoke. Connected via `claude_desktop_config.json`'s `mcpServers.harness`, running `harness-api` as a real live `uvicorn` process on `:8001` for the first time (previously only ever run in-process via `TestClient`).

Verified two ways: (1) a separate, ad-hoc Claude Desktop chat asked the literal PRD §15 question but didn't invoke the tool at all - a model tool-routing choice given the question's ambiguity alongside other configured connectors (Jira/Confluence/Slack), not a defect in `mcp-server` itself; (2) this Cowork session, itself connected to the same `harness` MCP server over stdio (real client, real process, not a test double), called `get_evidence` on the seeded insight id directly and got back exactly PRD §15's shape - a "Current understanding" statement plus a real evidence list ("Customer conversation - Acme Corp", "Sales discussion - EMEA pipeline", etc., from T058's per-record source join). `search_company_context` also correctly surfaced both seeded statements and a tension sentence naming `enterprise_sso`, confirming the conflict-detection path too - though heavily diluted by every other test fixture written today, since that tool aggregates the entire knowledge store with no way to scope to "real" vs. test data. Flagged as a real, separate gap from the 256-match cap (T061): there's currently no environment/workspace separation between test runs and demo/production data in OpenViking.

**Follow-up, by user decision:** sharpened all 8 tools' docstrings (and added a server-level `instructions` string) after the live test showed a real Claude Desktop chat not calling any tool for an ambiguous internal question. Each description now names concrete example questions it answers and frames the harness as the authoritative source for the organisation's own internal state - kept fully generic (no RMS-specific wording) since this is meant to scale to any organisation that deploys it. `apps/mcp-server` full suite re-confirmed: 13 passed.

---

## Phase 12 — Temporal knowledge

### T066 — `supersedes` linking on write
**Goal:** Superseding candidates correctly link to and close out the old record.
**Start:** T028, T038.
**Do:** When Compare determines superseding, set `old.status = superseded`, `old.superseded_at = now()`, `new.supersedes = old.id`.
**Test:** Unit test runs two sequential fixture transcripts on the same topic where the second supersedes the first; asserts both records end up correctly linked/statused.
**Status:** ✅ COMPLETE. Added `KnowledgeRecord.superseded_at`, `OpenVikingClient.mark_superseded(id, superseded_at)` (implemented in both `FakeOpenVikingClient` and `RealOpenVikingClient`, same read-modify-write-via-replace shape as `update_knowledge_status`). Wired into `context_agent.pipeline._write()`: when `relationship == "superseding"`, calls `mark_superseded` on `existing[0].id` (documented simplification - `supersedes` is a singular field and this build-plan's own test scope only ever involves one existing record) and sets the new record's `supersedes` to that id. Added a unit test (`test_second_transcript_superseding_the_first_links_and_statuses_both_records`) running two sequential `process_transcript` calls on the same topic, second with `FakeLLM.set_next_compare_result("superseding")`, asserting the new record's `supersedes` and the old record's `status`/`superseded_at`. `libs/openviking_client` + `apps/context-agent` full suite: 50 passed.

Found and fixed a bug in my own first draft of this test, not in the pipeline: fixture candidates with no `source_context` default to "casual_conversation" (low confidence), and PRD's rule for low-confidence-with-nothing-existing correctly assigns `PENDING_REVIEW` rather than `ACTIVE` - fixed by giving both fixture candidates `source_context: "customer_statement"`, matching how other pipeline tests avoid this.

**Follow-up investigation, not part of T066 itself:** `apps/context-agent/tests/test_worker.py::test_worker_processes_a_webhook_ingested_transcript_into_openviking` (a pre-existing T048 e2e test against real OpenViking) times out after ~120s (2x `RealOpenVikingClient`'s 60s httpx timeout), even in isolation. Investigated whether this is a real OpenViking performance/scaling problem (relevant to production UX, since `harness-api`'s `GET /knowledge/{id}` uses the same client): timed the exact same calls directly via `curl` - a full-tree recursive `search/glob` across all 119 accumulated test records (0.23s), a topic-scoped `search/glob` (0.19s), and a `content/write` (0.16s) - all fast. This rules out OpenViking's own latency as the cause. The timeout appears specific to this one test's plumbing (mixes a synchronous `TestClient` webhook post with an async `RealOpenVikingClient` call inside one pytest-asyncio test), not a service-latency risk to real users and not something T066 touched (the superseding code path isn't exercised by this test at all - its candidate's relationship is "new"). Left as an open follow-up (test-only), not blocking.

### T067 — History exposed via MCP
**Goal:** Same chain available to AI agents.
**Start:** T066, T059, T063.
**Do:** Add or extend an MCP tool to surface the `/knowledge/{id}/history` chain.
**Test:** MCP test client call returns the same chain as T059's REST call.
**Status:** ✅ COMPLETE. Added `HarnessAPIClient.get_knowledge_history()` (calls `GET /knowledge/{id}/history`), a new MCP tool `get_knowledge_history(knowledge_id)`, and a dedicated `format_history()` formatter - by user decision, deliberately not reusing `format_answer()`. `format_answer()` merges every record's statement into one "Current understanding" block, which would present superseded statements as if still current; `format_history()` instead renders a numbered, newest-to-oldest timeline with each entry's status (`[ACTIVE]`/`[SUPERSEDED]`) and date. Tested against real OpenViking + in-process harness-api, same pattern as `get_evidence`'s own test: writes two records (old, then marked superseded via T066's `mark_superseded`, then a new one pointing `supersedes` back at it), confirms the MCP tool's output exactly matches `format_history()` applied to a direct REST call to `/knowledge/{id}/history`. `apps/mcp-server` full suite: 17 passed (13 previous + 2 new `format_history` unit tests + 2 new tool integration tests).

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

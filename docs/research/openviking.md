# OpenViking Research Spike (S1)

Status: complete. Everything below was read directly from the official repo (`https://github.com/volcengine/OpenViking`, `main` branch) — the top-level README plus `docs/en/getting-started/03-quickstart-server.md`, `docs/en/api/01-overview.md`, `docs/en/api/02-resources.md`, `docs/en/api/03-filesystem.md`, `docs/en/api/06-retrieval.md`, `docs/en/concepts/08-session.md`, and the root `docker-compose.yml`. Nothing here is inferred from search snippets alone.

## 1. Repo and license

- Official repo: `https://github.com/volcengine/OpenViking` (volcengine org). 26.9k stars, 2.1k forks at time of research, actively released (v0.4.10 was latest at the time of the fetch).
- **License is split by component**:
  - Main project (the server/core, i.e. what we'd run and depend on): **AGPL-3.0**.
  - `crates/ov_cli`: Apache 2.0.
  - `examples/`: Apache 2.0.
  - `third_party/`: each under its own original license.
- **Flagging for Legal, not deciding myself**: AGPLv3 has a network-use clause — modifying AGPL-licensed server code and then offering it as a network service can trigger an obligation to make the modified source available to users of that service. We are not planning to modify OpenViking's own code (we'd run the official image and talk to it only over HTTP), which is the situation AGPL is generally least restrictive about, but this is a legal judgment call for RMS, not an engineering one. **This needs sign-off from RMS Legal before OpenViking goes into any production build**, per company policy on licensing/compliance questions. I have not asked Legal — flagging it here so it isn't missed.

## 2. What OpenViking actually is (this changes our architecture assumption)

Our architecture.md currently assumes OpenViking has "its own Postgres+pgvector database." **That's not correct.** OpenViking has no Postgres dependency at all. It stores everything in its own storage engine under a `viking://` virtual filesystem (backed by a local workspace directory, e.g. `"storage": {"workspace": "/home/you/openviking_workspace"}` in its config, or `./data` by default). Content, vectors, and metadata all live inside that engine, not in a relational database we could share or point at our Supabase instance. Concretely this means: there is no "share Postgres with Supabase" question to resolve — OpenViking's storage is fully separate and self-contained, and vendoring it changes nothing about Supabase's role (Supabase stays purely ours).

## 3. How to run it locally

Prerequisites per the README:
- Python 3.10+
- Rust toolchain (Cargo) and a C/C++ compiler — listed as required "for building RAGFS and CLI components from source." It's unclear from the docs whether a plain `pip install openviking` pulls prebuilt wheels for macOS (Apple Silicon) or needs local compilation. **This is untested — first real action item for you.**
- A configured embedding model + VLM (vision-language model) — OpenViking needs both for its own semantic pipeline. It supports local models via Ollama (which you already have running for our own `llm_router`), or cloud providers (OpenAI, Volcengine, Gemini, etc.) via API key.

Two ways to get it running:

**A. Native (pip), simplest first test:**
```bash
pip install openviking --upgrade --force-reinstall
openviking-server init      # interactive wizard; choose Ollama for local models
openviking-server doctor    # validates config before starting
openviking-server           # starts on http://0.0.0.0:1933
```
Verify with:
```bash
curl http://localhost:1933/health
# expect: {"status": "ok"}
```

**B. Docker (matches how we'd vendor it for the real build):**
The repo ships a `docker-compose.yml` at its root using the official image `ghcr.io/volcengine/openviking:latest`, exposing port 1933 directly (and 1934 via a bundled Caddy reverse proxy for HTTPS setups we don't need yet). It mounts `~/.openviking:/app/.openviking` for persistent config/data and has a built-in healthcheck. This is a clean fit for a `vendor/openviking` submodule + docker-compose service, as architecture.md already planned — the storage-model correction above is the only real change needed there.

## 4. Real HTTP API (not what we assumed)

OpenViking is a FastAPI-based HTTP service. All responses share one envelope:
```json
// success
{"status": "ok", "result": { ... }, "time": 0.123}
// error
{"status": "error", "error": {"code": "NOT_FOUND", "message": "..."}, "time": 0.01}
```
Auth: `Authorization: Bearer <key>` or `X-API-Key: <key>` header. Two key tiers — `root_key` for admin/account management, `user_key` for tenant-scoped data operations (the server resolves the tenant from the key automatically). `/health` and `/ready` never require auth.

**There is no `write_knowledge(record)` / `get_relevant_knowledge(topic)` concept in OpenViking's own API.** Its real primitives are:
- **Resources** — import a document/URL/file into the `viking://resources/` tree (`POST /api/v1/resources`), or write/update a plain text file directly (`POST /api/v1/content/write`, supports `mode: "create"` for a new file or `"replace"` for an existing one).
- **Search** — semantic vector search over whatever's stored (`POST /api/v1/search/find`, or `/search/search` for session-aware retrieval), plus `grep`/`glob` for exact/pattern matching.
- **Sessions** — a conversational-memory feature (`add_message` → `commit`) that runs **OpenViking's own** LLM-driven extraction/dedup pipeline and writes into its own fixed memory taxonomy (`profile`, `preferences`, `entities`, `events`, `identity`, `soul`, `cases`, `trajectories`, `experiences`). This is a parallel, competing pipeline to the one we already built in `context_agent` (our own Extract/Retrieve/Compare/Classify/Write, with PRD §10's rule-based confidence and §17's human-review gating).

**Recommended mapping (proposal, not yet built — flagging this as a design decision for you to confirm before T033)**: don't use OpenViking's session/memory-extraction feature at all. Use it purely as a structured, vector-searchable file store for records that `context_agent` itself has already classified and scored. Concretely:
- `OpenVikingClient.write_knowledge(record)` → `POST /api/v1/content/write` with `uri: "viking://resources/knowledge/{record.topic}/{record.id}.json"`, `content: record.model_dump_json()`, `mode: "create"` (or `"replace"` on update).
- `OpenVikingClient.get_relevant_knowledge(topic)` → `POST /api/v1/search/find` with `query: topic`, `target_uri: "viking://resources/knowledge/"`, then `GET /api/v1/content/read?uri=...` each match and `KnowledgeRecord.model_validate_json(...)` it back.
- `OpenVikingClient.get_knowledge_by_id(id)` → direct `GET /api/v1/content/read` if we know the topic-scoped URI, or `POST /api/v1/search/glob` with `pattern: "**/{id}.json"` if we don't.

This keeps all of our PRD-mandated business logic (confidence rules, `pending_review` gating) exactly where it is today, and uses OpenViking only for what it's actually good at: storage + semantic retrieval. It skips OpenViking's session/memory/VLM machinery entirely, which also reduces how much of the AGPL'd code paths we'd even be exercising.

### Example: write a knowledge record
```bash
curl -X POST http://localhost:1933/api/v1/content/write \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "uri": "viking://resources/knowledge/enterprise_sso/K-existing-sso.json",
    "content": "{\"id\":\"K-existing-sso\",\"topic\":\"enterprise_sso\",\"statement\":\"SSO is an occasional customer request\",\"status\":\"active\",\"confidence\":0.5}",
    "mode": "create",
    "wait": true
  }'
```
Response (real shape, from the docs):
```json
{
  "status": "ok",
  "result": {
    "uri": "viking://resources/knowledge/enterprise_sso/K-existing-sso.json",
    "root_uri": "viking://resources/knowledge/enterprise_sso",
    "context_type": "resource",
    "mode": "create",
    "written_bytes": 132,
    "content_updated": true,
    "semantic_status": "complete",
    "vector_status": "complete",
    "queue_status": {"Semantic": {"processed": 1, "error_count": 0, "errors": []}, "Embedding": {"processed": 1, "error_count": 0, "errors": []}}
  }
}
```

### Example: read it back (semantic search, then full read)
```bash
curl -X POST http://localhost:1933/api/v1/search/find \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"query": "enterprise_sso", "target_uri": "viking://resources/knowledge/"}'
```
```json
{
  "status": "ok",
  "result": {
    "resources": [
      {"uri": "viking://resources/knowledge/enterprise_sso/K-existing-sso.json", "score": 0.87, "level": 2, "abstract": "...", "context_type": "resource"}
    ],
    "memories": [], "skills": [], "total": 1
  }
}
```
Then:
```bash
curl "http://localhost:1933/api/v1/content/read?uri=viking://resources/knowledge/enterprise_sso/K-existing-sso.json" \
  -H "X-API-Key: your-key"
```
returns `{"status": "ok", "result": "{...the raw JSON we wrote...}"}`.

## 5. Multi-tenant support

Yes, natively, but at the **account/user** level, not as free-form metadata on individual records:
- Admin API: `POST /api/v1/admin/accounts` (create a workspace + first admin, ROOT only), `.../accounts/{id}/users` (register/list/remove users), `.../users/{id}/key` (regenerate a user's key).
- The server resolves tenant identity from the API key itself (a `user_key` is bound to one account/user). Optional headers (`X-OpenViking-Account`, `X-OpenViking-User`) exist for trusted-gateway setups that need to assert identity explicitly.
- There's also a generic `filter: Dict` parameter on `find`/`search` described only as "Metadata filter" — the docs don't expand on its schema, so I can't yet say whether it supports arbitrary custom fields (e.g. an RMS `org_id` or `department`) beyond account/user scoping. **Unconfirmed — worth a quick hands-on test once the server is running**, rather than something to build our schema around yet.

## 6. Concrete proof it runs (S1's required evidence)

Confirmed locally on 2026-09-24, in a dedicated `~/.openviking-venv` virtualenv (needed because the Mac's system Python is Homebrew-managed and blocks a bare `pip install`):

```bash
pip install openviking --upgrade --force-reinstall   # succeeded, no Rust/C++ toolchain errors
openviking-server init                                # chose "Recommended local setup (all-Ollama)", host 127.0.0.1, port 1933
openviking-server doctor                              # All checks passed (Native Engine, AGFS, Auth, Embedding, VLM, Ollama, VikingBot, Disk)
openviking-server                                      # "OpenViking HTTP Server is running on 127.0.0.1:1933"
```
```bash
curl http://localhost:1933/health
# {"status":"ok","healthy":true,"version":"0.4.21","auth_mode":"dev"}
```

This resolves open item #1 from the original draft of this section: `pip install openviking` installed cleanly on this Mac with no Rust/Cargo/C++ toolchain errors. The `init` wizard pulled three Ollama models automatically (`qwen3-embedding:0.6b`, `qwen3.5:4b`, `guoxuter/ov_intent_analysis_sft:v7_q8`) — separate from whatever model our own `llm_router` already uses locally; the two don't conflict, they're just both served by the same local Ollama daemon.

## 7. Remaining open items before T033 (real OpenVikingClient) starts

1. **Confirm the `write_knowledge` → `content/write` mapping in §4 with me before I build the real `OpenVikingClient`** — already confirmed by you; noting it here as the design decision T033+ will implement against.
2. **AGPL sign-off from Legal** — separate from the engineering work, flagged in §1. Still outstanding.
3. **Test the `filter` parameter** once we're writing real records, to see if it gives us anything closer to custom multi-tenant metadata than account/user scoping does.

## Sources

All of the following were fetched directly from the `main` branch on 2026-09-24:
- https://github.com/volcengine/OpenViking (README)
- https://github.com/volcengine/OpenViking/blob/main/docker-compose.yml
- https://github.com/volcengine/OpenViking/blob/main/docs/en/getting-started/03-quickstart-server.md
- https://github.com/volcengine/OpenViking/blob/main/docs/en/api/01-overview.md
- https://github.com/volcengine/OpenViking/blob/main/docs/en/api/02-resources.md
- https://github.com/volcengine/OpenViking/blob/main/docs/en/api/03-filesystem.md
- https://github.com/volcengine/OpenViking/blob/main/docs/en/api/06-retrieval.md
- https://github.com/volcengine/OpenViking/blob/main/docs/en/concepts/08-session.md

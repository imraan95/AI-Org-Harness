# Anarlog Webhook Research Spike (S2)

Status: complete for `webhook.test` — a real webhook was triggered against a running `ingestion-service` (T044) through an ngrok tunnel and captured (see §8). The exact nested `note`/`summaries`/`participants` field shapes for real `meeting.completed`/`note.enhanced` events are still unconfirmed (would need an actual recorded meeting — optional follow-up, not blocking T045). Sourced from Anarlog's own docs site (`docs.anarlog.so`), its OpenAPI schema, its GitHub repo, and this real captured delivery — nothing here is inferred from search snippets alone.

## 1. What Anarlog actually is

Anarlog (`github.com/fastrepl/anarlog`, formerly "Hyprnote") is a real, open-source (MIT), **local-first desktop app** — not a hosted SaaS meeting bot. It's a Rust/Tauri desktop application (macOS/Windows/Linux) that records a meeting's microphone + system audio *without joining the call as a bot*, transcribes on-device, and stores the canonical meeting data (note, transcript, summary) in a local SQLite database on the user's machine.

This matches what `docs/prd.md` §13 already says (on-device transcription, local storage, API/MCP/CLI/webhooks) — **no PRD/architecture correction needed here**, unlike the OpenViking storage-model surprise in S1. The one real gap is architectural, not documentational: **webhooks are pushed from each user's local desktop app instance**, not from a central Anarlog server. See §3 and §6.

Optional hosted features exist (end-to-end-encrypted Cloud Sync, and a separate opt-in "Cloud API & Connectors" for Anarlog Pro subscribers), but the MVP's webhook path doesn't need either of those.

## 2. Where webhooks are configured

Per-installation, in the desktop app itself: **Settings → Developers → Webhooks**. You enter an `https://` URL and get a one-time-shown signing secret (`whsec_...`). One installation can register up to 64 endpoints, and a new endpoint is subscribed to **all** events (no per-event filtering).

This means the webhook URL has to be a real public HTTPS endpoint reachable from wherever the desktop app runs — there's no way to register a callback URL on some central Anarlog dashboard the way you'd register one with, say, Stripe or GitHub. For local dev/testing this means an HTTPS tunnel (ngrok, Cloudflare Tunnel, etc.) pointed at `ingestion-service`'s `/webhooks/anarlog` (T044). For production rollout, every RMS employee whose meetings should feed the harness needs their own Anarlog desktop app configured with a webhook pointing at our real ingestion-service URL — this is a per-user setup/rollout question, not just an engineering one (flagging for product planning, not deciding here).

## 3. Events and payload envelope

Anarlog delivers events as JSON `POST` requests **only while the desktop app is running**:

| Event | Fires when |
|---|---|
| `meeting.completed` | A recording session finishes. |
| `note.enhanced` | An AI summary is generated for a meeting. |
| `webhook.test` | Manually triggered from the settings page. |

Envelope (confirmed verbatim from the docs):
```json
{
  "id": "evt_...",
  "event": "note.enhanced",
  "created_at": "2026-07-28T09:00:00.000Z",
  "data": {
    "meeting": {
      "id": "...",
      "title": "...",
      "note": {"...": "..."},
      "summaries": ["..."],
      "participants": ["..."],
      "action_items": ["..."]
    },
    "transcript_text": "..."
  }
}
```

**Important correction to what T045's normaliser can assume**: `transcript_text` is a single flat string — the docs give no indication of per-speaker-turn or per-word timestamp structure inside the webhook payload itself. There is no `speaker`/`start`/`end` field shown anywhere in the webhook docs. If PRD/build-plan work downstream (e.g. showing "who said what when") needs that, it is **not available from the webhook** — see §6.

`note.enhanced` fires only after Anarlog's own AI has produced a summary, meaning `meeting.completed` alone may arrive with a real transcript but no note/summary yet — worth deciding in T045 whether we process on `meeting.completed`, wait for `note.enhanced`, or handle both.

## 4. Signature verification (confirmed, enough detail to implement T049 without guessing)

Every delivery includes these headers:

| Header | Content |
|---|---|
| `x-anarlog-event` | Event name. |
| `x-anarlog-delivery` | Unique delivery ID (use for de-dup on retries). |
| `x-anarlog-timestamp` | Unix timestamp, seconds (use for replay protection). |
| `x-anarlog-signature` | `sha256=<hex>` — HMAC-SHA256 of the **raw** request body, keyed with that endpoint's `whsec_...` secret. |

Verification (official example, Node.js — the Python equivalent is a direct port: `hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()`, compared with `hmac.compare_digest`, not `==`):
```js
const expected = `sha256=${crypto.createHmac("sha256", secret).update(rawBody).digest("hex")}`;
const valid = timingSafeEqual(signature, expected);
```
Anarlog's own guidance: verify over the **raw, unparsed** body (not the re-serialized JSON), reject stale `created_at` values, and store each payload's `id` to dedupe retries.

## 5. Retry, timeout, and idempotency implications for T046/T047

- Delivery timeout: **10 seconds**. If `ingestion-service` doesn't respond in time, Anarlog treats it as failed.
- Retries: failed real-event deliveries (`meeting.completed`, `note.enhanced`) retry after **5s, then 30s** (3 attempts total). `webhook.test` makes exactly **one** attempt, no retry.
- Anarlog runs at most **4 concurrent deliveries** and delivers to at most **64 endpoints per event**.
- **T044/T046 must be idempotent on the envelope's `id`** (or `x-anarlog-delivery`) — a retry after a slow-but-eventually-successful first attempt is a real possibility, not just a theoretical one.

## 6. Known gaps — flagging, not deciding

1. **Events are dropped, not queued, while the desktop app is closed.** Per the docs verbatim: *"Deliveries only run while the desktop app is open. Events that occur while it is closed are dropped, not queued for later delivery."* This is a real coverage gap for an MVP relying solely on webhooks — if someone records a meeting and closes Anarlog before `note.enhanced` fires (or before opening it again), that event is gone. The Cloud API (`GET /v1/meetings`, requires Anarlog Pro + explicit opt-in per user) could serve as a backfill/reconciliation path, but that's a product decision (extra subscription cost, extra opt-in, extra data-handling disclosure) beyond this spike's scope — flagging for you/PRD, not deciding.
2. **No structured speaker-turn or word-level timestamp data in the webhook payload** — only flat `transcript_text`. Word-level timing (via a `words` array) exists only behind the separate, Pro-gated Cloud API's `GET /v1/meetings/{id}/transcript` endpoint, and even there I could not confirm from the OpenAPI schema whether individual words carry a speaker label (the one `words`-shaped schema I found, `BatchWord`, belongs to a different, on-device batch-transcription endpoint, not this one). If per-speaker attribution turns out to matter for the harness, this needs a follow-up check against a real Cloud API response — not assumed.
3. **Exact field shapes for `note`, `summaries[]`, `participants[]` are not published in the docs** — only `action_items[]` has a confirmed schema, pulled from Anarlog's Cloud API OpenAPI spec (`https://api.anarlog.so/openapi.json`):
   ```json
   {"id": "string", "assignee_human_id": "string", "status": "string", "text": "string", "due_at": "string", "completed_at": "string | null"}
   ```
   This is the Cloud API's shape for action items, not confirmed byte-identical to what's embedded in a webhook payload's `data.meeting.action_items` — likely the same underlying model, but unconfirmed. `note` and `summaries` bodies are described elsewhere in the docs as "markdown" (not structured JSON), which at least rules out expecting rich nested fields there.
4. Whether `data.meeting` includes an explicit meeting date/attendee-list-with-names (vs. just `participants`) isn't shown in the truncated example in the docs. Needs a real payload to confirm.

## 7. Full picture of programmatic access, and whether it supports per-user tenancy

Anarlog exposes four ways to get data out, all confirmed from `reference/cli.md`, `reference/mcp.md`, `reference/webhooks.md`, `reference/api-cloud.md`:

| Surface | Runs where | Scope | Push or pull |
|---|---|---|---|
| **Webhooks** | Inside the desktop app, per-installation | Whatever's in that one person's local Anarlog | Push (only while that person's app is open) |
| **CLI** (`anarlog meetings ...`) | A process on that person's own machine | `--source local` reads their local SQLite DB; `--source cloud` reads their own opted-in Cloud snapshot via `anarlog auth login` | Pull, but the process has to run on/near their machine |
| **Local MCP** (`anarlog mcp`) | stdio process on that person's own machine | Same local DB as the CLI | Pull, same locality constraint as CLI |
| **Cloud API / remote MCP** | Hosted (`api.anarlog.so`) | One person's account, keyed by their own `anl_...` bearer key — requires that person to have Anarlog Pro and to explicitly opt in (uploads a server-readable snapshot of their meetings to Anarlog's cloud) | Pull, reachable from our own servers with no agent needed on their machine |

**The key finding for your tenancy question: Anarlog has no multi-tenant concept at all, in any of these surfaces.** Every one of them is scoped to exactly one person's own data, authenticated as that one person (their local DB, or their own Cloud key). There is no "workspace" or "org" object, and — as far as the docs and the webhook envelope show — **no employee/user/tenant identifier anywhere in a webhook payload's body**. If ten RMS employees each webhook into the same `ingestion-service` endpoint, the payload alone doesn't tell you which of them it came from.

**What this means for a per-user view in the webapp**: multi-tenancy has to be something *we* build at the ingestion boundary, not something Anarlog hands us. Only the webhook and Cloud API surfaces are realistically usable from a central web app (CLI/local MCP both require a process running on each employee's own laptop, which is a much bigger footprint than this MVP is scoped for). Concretely, for webhooks — the two practical options, neither yet decided:
- **Per-user webhook identity (recommended direction, not yet built)**: mint a unique secret (and optionally a unique URL path, e.g. `/webhooks/anarlog/{rms_user_id}`) per RMS employee when they connect Anarlog in our webapp, store that mapping in our own Supabase tables, and have each employee paste *their own* URL+secret into *their own* Anarlog Settings → Developers → Webhooks. The employee identity comes from **which secret validated the signature**, not from anything in the payload body. This is the only surface that supports real-time push per user.
- **Per-user Cloud API key**: each employee enables Cloud API & Connectors in their own Anarlog (needs Pro), gives us their `anl_...` key, and we poll `GET /v1/meetings` per employee on a schedule. This avoids the "app must be open" gap (§6.1) but costs each employee a Pro subscription plus an explicit extra data-sharing opt-in (a separate server-readable copy of their meetings on Anarlog's own cloud) — a procurement/privacy conversation, not an engineering default.

**This is a real gap against the current build-plan**: T044 as built has one fixed route (`POST /webhooks/anarlog`) with no per-user secret or identity concept, because S2 was blocking exactly this finding. T046 onward (persisting to Supabase) will need a `source_id`/`workspace_id`-style mapping from "which secret fired" to "which RMS employee" before this can support more than one person. `libs/knowledge_model`'s existing permissions scaffold (`workspace_id`, `source_id` — see T039/ADR notes) already has fields that could carry this; it just isn't wired up to anything Anarlog-specific yet. Flagging this for you to decide before T045/T046 get built, rather than silently building single-tenant and redoing it later.

## 8. Concrete proof (S1-equivalent) — done

Confirmed live on 2026-09-24: Anarlog desktop app installed fresh on macOS, tunnelled to a locally running `ingestion-service` (T044) via `ngrok http 8000 --url https://semiresinous-fruitlike-wilhemina.ngrok-free.dev`, registered under Anarlog's Settings → Developers → Webhooks as `https://.../webhooks/anarlog`, then triggered with the **Test** button. Real captured delivery, logged by T044's endpoint:

```json
{
  "id": "evt_30d1dcbb059a417892be7353ec5e9cd4",
  "event": "webhook.test",
  "created_at": "2026-09-24T06:45:53.265Z",
  "data": {"message": "This is a test delivery from Anarlog."}
}
```

This confirms, with real values rather than docs prose: the envelope's `id` format (`evt_` + a 32-char hex string), the `created_at` format (ISO 8601 with milliseconds, `Z` suffix), and — a detail the docs didn't spell out — that **`webhook.test`'s `data` is just `{"message": "..."}`, not a `meeting` object**. Only real `meeting.completed`/`note.enhanced` events carry the `data.meeting`/`data.transcript_text` shape shown in §3. T044 responded `200 OK` within the endpoint's 10s timeout, so no retry was triggered.

One real gap this surfaced and fixed in the code itself, not just the docs: `apps/ingestion-service/src/ingestion_service/main.py`'s `logger.info(...)` call was silently dropped on a real run — Python's root logger defaults to `WARNING` and nothing had configured it otherwise. `pytest`'s `caplog` fixture in T044's test masked this by forcing capture regardless of level, so the test passed despite production logging being broken. Fixed with a `logging.basicConfig(level=logging.INFO)` call in `main.py`; re-confirmed the payload now prints to the console on a real request.

**Signature verification was not exercised in this test** — `webhook.test` deliveries are sent, and the desktop app does sign them with the endpoint's `whsec_...` secret per §4's headers (unconfirmed by direct inspection here, since the test above only checked the logged body, not the request headers). T049 should log/inspect `x-anarlog-signature` etc. on the first real implementation pass to confirm this in practice, rather than assume it from docs prose alone.

**Not yet done, optional**: recording one throwaway real meeting to capture an actual `meeting.completed`/`note.enhanced` payload and resolve §6.3–§6.4's open items (exact `note`/`summaries`/`participants` shapes) with real data. Not blocking T045 — the normaliser can be built against the documented envelope shape and adjusted once a real meeting payload is seen.

## Sources

Fetched directly on 2026-09-24:
- https://docs.anarlog.so (docs index / llms.txt)
- https://docs.anarlog.so/reference/webhooks — events, envelope, signature scheme, retry/limits
- https://docs.anarlog.so/reference/api-cloud — Cloud API, REST endpoints, remote MCP
- https://docs.anarlog.so/reference/cli — CLI commands, `--source local|cloud|auto`, auth model
- https://docs.anarlog.so/reference/mcp — local MCP tools/resources
- https://api.anarlog.so/openapi.json — `ActionItem` schema
- https://github.com/fastrepl/anarlog — repo README, license (MIT), local-first architecture confirmation

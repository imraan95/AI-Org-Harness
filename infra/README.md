# infra

Local dev infrastructure that isn't Supabase (Supabase runs via its own CLI) - currently just the vendored OpenViking service's docker-compose entry, added in Phase 6.

## Ollama contention with `libs/llm_router`'s tests - fixed (T078)

OpenViking's container keeps its own Ollama models (`qwen3.5:4b`, `qwen3-embedding:0.6b`, `guoxuter/ov_intent_analysis_sft`) warm via background health checks. If our own code shares that same Ollama daemon (the default port, 11434), this doesn't just slow things down - live testing found it can wedge the daemon entirely (`ollama ps` shows a model stuck in "Stopping..." indefinitely, unresponsive even to unrelated requests, not just slow), repeatedly and reproducibly.

**The fix:** run a second, independent `ollama serve` process on its own port, dedicated to our own code, and point `OLLAMA_BASE_URL` at it. In its own terminal tab, left running:
```
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```
Then set `OLLAMA_BASE_URL=http://127.0.0.1:11435` (already in the root `.env.local` - `set -a && source .env.local && set +a` before running tests/scripts). Model files are shared on disk regardless of which port serves them, so nothing needs re-pulling. OpenViking's container keeps using the default port unaffected (configured via `openviking-config/ov.conf`'s `host.docker.internal:11434`).

With this in place, the full `libs/llm_router` suite runs in under 20 seconds with OpenViking's container up and busy - previously the same suite, same conditions, could time out for 25+ minutes.

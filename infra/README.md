# infra

Local dev infrastructure that isn't Supabase (Supabase runs via its own CLI) - currently just the vendored OpenViking service's docker-compose entry, added in Phase 6.

## Note: Ollama contention with `libs/llm_router`'s tests

OpenViking's container keeps its own Ollama models (`qwen3.5:4b`, `qwen3-embedding:0.6b`, `guoxuter/ov_intent_analysis_sft`) warm via background health checks, on the same shared local Ollama daemon our own `llm_router` uses (`llama3.2`). On a laptop's limited GPU/memory, this can make Ollama slow to swap in `llama3.2` for `libs/llm_router/tests/test_ollama.py`, timing out well past its 120s timeout - confirmed by testing (240s+ timeout with the container up, 4.44s the moment it was stopped).

**If `test_ollama.py` (or `uv run pytest` generally) times out or is unusually slow:** stop the OpenViking container first (`docker compose -f infra/docker-compose.yml down`), then rerun. You don't need it running for the regular test suite - only for `scripts/seed.py` and `libs/openviking_client`'s real integration tests.

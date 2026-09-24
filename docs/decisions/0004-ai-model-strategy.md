# 0004 — AI model strategy: open-weight default, swappable via a router

**Status:** Accepted
**Date:** 2026-09 (early planning)
**Context:** PRD §11.

## Decision

The product does not depend on a proprietary frontier model. Default model is open-weight and runs locally or inexpensively — initially a Llama-family model (or comparable), served via Ollama. Every service calls a common `LLM` interface (`generate`, `extract`, `classify`, `compare`, `summarise`) rather than a specific provider's SDK; `libs/llm_router` is the only place model choice is configured. A frontier API backend is supported but optional, for tasks where the cheap local model isn't capable enough.

## Why

Avoids lock-in to one vendor's API/pricing/availability, and keeps the MVP runnable without a paid API key. Routing per-task (small model for extraction/classification, optionally a larger one for harder synthesis/contradiction detection) follows the PRD's "use the cheapest capable model for each task" principle.

## Consequence

`OllamaLLM` only implements `extract`/`classify` so far (the tasks the pipeline actually calls today); `generate`/`compare`/`summarise` raise `NotImplementedError` until a later task wires them up. Local inference is not fast — cold-start model loads took 60–120s+ during actual testing (T020, and again when OpenViking's own local VLM/embedding models were set up in T034) — which is why ingestion is deliberately decoupled from processing via the `jobs` table (architecture.md §6): a slow model call never blocks the Anarlog webhook or the web app, it only delays how soon a meeting's knowledge becomes queryable.

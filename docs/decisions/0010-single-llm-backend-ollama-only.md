# 0010 — Single LLM backend (Ollama only), no per-task tiering, no frontier option

**Status:** Accepted
**Date:** 2026-09-26
**Context:** Explicit user decision to simplify the codebase ahead of deployment: "we will be supporting only 1 llm choice. no multi-llm complication." Supersedes 0004's "frontier API optional, per-task tiering" clauses.

## Decision

`get_llm()` (`libs/llm_router/src/llm_router/router.py`) always returns `OllamaLLM()`. No `FRONTIER_API_KEY` branching, no `FrontierLLM` class in the codebase at all, no per-task model tiering (`get_model_for()`, `DEFAULT_TASK_TIERS`, `DEFAULT_TIER_TO_MODEL` - all deleted). `OLLAMA_MODEL` (already existing) remains the one and only model-selection lever, applied uniformly to every task.

The abstract `LLM` interface (`interface.py`) and the `FakeLLM` test double are unchanged and stay. Every call site (`context_agent.pipeline`) already went through the interface, not a concrete class - that's what keeps "switch models later" a one-function change in `router.py` rather than an architectural one, per the user's explicit requirement when making this decision.

## Why

Two things made this an easy call, not just a preference:

1. **The per-task tiering system was already dead code.** `OllamaLLM.__init__` picks one `self._model` (from `OLLAMA_MODEL`, default `llama3.2`) and every method (`extract`, `classify`, `compare`, `match_topic`) sends that same model via `_call()`. Nothing in the codebase ever called `get_model_for()` outside its own tests - not `OllamaLLM`, not `context_agent.pipeline`. "One model for every task" was already true in actual runtime behavior; this decision just deletes the orphaned config layer that documented an intent (0004's "route per-task, small model for extraction, optionally a larger one for synthesis") that was never wired up.
2. **`FrontierLLM` had nothing real to lose.** Only `generate()` was ever implemented; `extract`/`classify`/`compare`/`match_topic` all raised `NotImplementedError` since the class was added. Unlike OpenViking (kept dormant in `docs/decisions/0009` because it was a real, working, tested alternative), there was no working functionality being discarded here - just an unfinished branch and the `get_llm()` logic that would pick it.

Beyond those two specific findings, the general reasoning tracks 0009's: less surface area to maintain, fewer paths to keep correct, and one less "which way did this get configured" question when reading the code or debugging a real run.

## What changed, concretely

- `get_llm()` - simplified to `return OllamaLLM()`, no env var check, no import of a frontier class.
- Deleted: `libs/llm_router/src/llm_router/frontier.py`, `libs/llm_router/tests/test_frontier.py`.
- Deleted from `router.py`: `get_model_for()`, `DEFAULT_TASK_TIERS`, `DEFAULT_TIER_TO_MODEL`.
- `libs/llm_router/src/llm_router/__init__.py` - `FrontierLLM` and `get_model_for` removed from imports/`__all__`.
- `libs/llm_router/tests/test_router.py` - rewritten to a single assertion (`get_llm()` returns `OllamaLLM`), replacing the now-meaningless tier-override tests.
- `interface.py`, `fake.py`, `ollama.py`, `test_ollama.py`, `test_interface.py`, `test_fake.py` - untouched. The interface still declares `generate`/`extract`/`classify`/`compare`/`match_topic`/`summarise`/`embed`; `OllamaLLM` still implements what it already implemented.

## Consequence for `docs/decisions/0004-ai-model-strategy.md`

0004's "frontier API backend is supported but optional" and implicit per-task-tiering framing are superseded by this decision. 0004 is left in place as a historical record of the original plan (with a short pointer added to this ADR), not rewritten - matching how 0009 treated the OpenViking research/decisions it superseded.

## Alternatives considered

- **Keep `FrontierLLM` dormant, like OpenViking.** Rejected - OpenViking was worth preserving dormant because it was a complete, working, tested implementation someone might want back. `FrontierLLM` was an unfinished stub; keeping unfinished, untested code around "just in case" isn't the same trade.
- **Keep the tiering system but collapse it to a single tier.** Rejected as unnecessary ceremony - since nothing ever called `get_model_for()`, keeping a one-tier version of it would just be dead code with fewer lines instead of no dead code at all.

## Revisit when

Switching to a different Ollama model needs no code change - just `OLLAMA_MODEL`. Switching to a different backend entirely (a frontier API, a different local runtime) means writing one new class implementing `LLM` and changing `get_llm()`'s single return line - by design, per this decision's own requirement, not a rewrite of `context_agent.pipeline` or anything that calls it.

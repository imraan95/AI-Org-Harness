# 0012 — `match_topic()` reliability: a targeted model swap, plus a deterministic canonicalization pre-filter

**Status:** Accepted
**Date:** 2026-09-26
**Context:** Built `scripts/eval_pipeline_accuracy.py` (a real eval harness against the live pipeline, real Ollama, a scoped view of the real Postgres knowledge store) to get an actual accuracy number on the pipeline instead of relying on ad hoc manual walkthroughs (T075/T076). First real run: topic-matching accuracy 40.9%, with every "has existing knowledge" case wrongly classified as "new" - `match_topic()` (0008) never bridged a single topic-name variant.

## Decision

Two changes, both scoped narrowly to the specific failure they fix:

1. **`match_topic()` calls a different model than everything else.** `DEFAULT_OLLAMA_MATCH_TOPIC_MODEL = "qwen3.5:4b"` (`libs/llm_router/src/llm_router/ollama.py`), used only by `match_topic()` via a new optional `model` parameter on `OllamaLLM._call()`. Every other call (`extract`, `classify`, `compare`) keeps using `DEFAULT_OLLAMA_MODEL` (`llama3.2`, via `OLLAMA_MODEL`). This is a deliberate, narrow exception to `docs/decisions/0010-single-llm-backend-ollama-only.md`'s "one model for every task" - not a reversal of it.
2. **A deterministic, zero-LLM canonicalization pre-filter** (`apps/context-agent/src/context_agent/topic_canonicalize.py`, `canonicalize_topic()`) runs between the exact-string match and the `match_topic()` LLM fallback in `pipeline._retrieve()`. It normalizes topic strings and requires either an exact normalized-key match or at least 2 distinct shared tokens (of length ≥ 3, excluding a generic-word stoplist) between candidate and existing topic before calling it a match - catching formatting/wording variants for free, with no model call at all.

## Why

### The model swap

`match_topic()`'s original design (0008: pairwise yes/no, `temperature: 0`) was sound - the eval harness proved the *model*, not the mechanism, was the problem. Real raw-`curl` reproduction against `llama3.2` on a clean, unambiguous pair ("GDS connectivity" vs. "gds_connectivity" - same subject, pure formatting difference) got a confident, instant "No". Two rounds of prompt tuning were tried before touching the model:

- **Attempt 1** added a single positive example (same subject, different formatting) to the prompt. This overcorrected: the model started confidently matching genuinely unrelated phrases too (e.g. "Mobile push notifications" vs. "Enterprise SSO").
- **Attempt 2** added a negative example alongside the positive one, so the model had both signals to calibrate against. Same confident, instant, wrong answer on the same pair.

Two prompt rewrites producing the same wrong answer, both times via a near-instant single-token response, is the signature of a capability ceiling, not a wording problem - confirmed by then testing the identical pairs against `qwen3.5:4b`, which reasoned through them correctly (visible chain-of-thought, ~15-25s/call vs. `llama3.2`'s ~0.1s).

Real eval-harness numbers, before/after: topic-matching accuracy **40.9% → 86.4%**.

### The canonicalization pre-filter

Ported the *idea*, not the code, from `supermemoryai/company-brain`'s open-sourced `canonicalizeProposedTags`/`canonicalMatch` (`tags.ts`) - a deterministic, same-kind-scoped, token-overlap cleanup pass they run after their own (closed, hosted) model proposes a tag. Two motivations, not one:

1. **Cost.** Every exact-match miss today calls `match_topic()` once per existing distinct topic (0008's own documented cost model). A cheap pre-filter that resolves formatting-only variants without any model call at all reduces that N-calls-per-miss cost for the common case, before it becomes a real problem at scale (0008's own "Revisit when" condition).
2. **It's genuinely more reliable for this narrow case than an LLM call.** `match_topic()`, even fixed, is still a probabilistic judgment. "SSO for Enterprise Customers" vs. "enterprise_sso" being the same subject is a deterministic fact about the strings, not something that needs asking a model at all.

**A real false-positive bug was found and fixed before shipping**, via self-testing against the eval harness's own near-miss cases (not asked for - done proactively, mirroring the discipline that caught the model-swap's own two failed attempts): a first draft matched on any single shared token, which incorrectly matched "Dynamic currency conversion" onto "dynamic_pricing_rules" (sharing only "dynamic") and "Maintenance mobile app" onto "housekeeping_mobile_app" (sharing only "mobile"). Fixed by requiring `_MIN_MATCHED_TOKENS = 2`, re-verified against all 4 near-miss scenarios plus both genuine-match scenarios before ever running it against the real eval harness.

## What changed, concretely

- `libs/llm_router/src/llm_router/ollama.py` - `DEFAULT_OLLAMA_MATCH_TOPIC_MODEL`; `OllamaLLM._call()` gains an optional `model` parameter; `match_topic()` passes it, every other method doesn't.
- `apps/context-agent/src/context_agent/topic_canonicalize.py` (new) - `canonicalize_topic(candidate_topic, existing_topics) -> str | None`, pure function, no I/O.
- `apps/context-agent/tests/test_topic_canonicalize.py` (new) - formatting-variant cases, a genuine-paraphrase case, and 4 explicit false-positive-trap regression tests for the single-shared-generic-word failure mode above.
- `apps/context-agent/src/context_agent/pipeline.py` - `_retrieve()` calls `canonicalize_topic()` between the exact-match check and the `match_topic()` fallback.
- `apps/context-agent/tests/test_pipeline.py` - `test_retrieve_falls_back_to_llm_topic_matching_when_exact_match_misses` split in two: one confirming the canonicalizer now resolves the "SSO for Enterprise Customers"/"Enterprise SSO" pair with zero `match_topic()` calls (a real, intended behavior change - the old test's exact case is now handled before the LLM is ever asked), one preserving genuine LLM-fallback coverage with a token-disjoint pair ("Time off rules"/"Vacation policy").
- `scripts/eval_pipeline_accuracy.py` (new) - the eval harness itself. Notably, its own `_reconstruct_candidates()` diagnostic had to be updated when the canonicalizer was added: it works by replaying *logged* proxy calls, but `canonicalize_topic()` is a pure function with no logged side effect, so the harness now independently replicates that exact call (same inputs `pipeline.py` uses) rather than trying to infer it after the fact. Caught via a real, initially-alarming apparent regression (86.4% → 50.0%) that traced back to the harness's own blind spot, not the pipeline - documented here so the same mistake isn't repeated if `_retrieve()`'s resolution logic changes again.

## What we tried and rejected

Covered under "Why" above (single-example prompt, two-example prompt, single-shared-token canonicalization) rather than repeated here.

## Alternatives considered

- **Vector/semantic similarity for topic matching**, instead of either an LLM call or string canonicalization. Already tried and rejected for this exact purpose in 0008 (OpenViking's semantic search measured near-random on our data shape) and not revisited here - nothing in this investigation surfaced new evidence that would change that finding.
- **A single "pick one from this list" LLM prompt** instead of pairwise yes/no. Already rejected in 0008 for the same unreliability reason; not revisited.

## Revisit when

The canonicalizer's `_MIN_MATCHED_TOKENS = 2` threshold and stoplist were tuned against this project's current eval cases - if real production topics start producing new false positives or false negatives, tune there first, not by touching `match_topic()`. If `qwen3.5:4b` itself is ever swapped out project-wide, re-verify `match_topic()`'s accuracy against the eval harness before assuming the new model inherits the same fix.

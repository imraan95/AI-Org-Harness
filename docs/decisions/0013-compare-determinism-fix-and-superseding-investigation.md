# 0013 — `compare()`: shipped a determinism fix; investigated but did not solve the superseding/contradicting confusion

**Status:** Partially resolved - determinism fix shipped; the accuracy problem is documented, unsolved, and left as an open product decision (see "Revisit when")
**Date:** 2026-09-26/27
**Context:** `scripts/eval_pipeline_accuracy.py` (0012) measured `compare()`'s relationship-classification accuracy at 63.6%, with real confusion between `contradicting`/`superseding`/`corroborating` - a second, separate problem from the topic-matching one 0012 fixed.

## Decision (the part that shipped)

`compare()` (`libs/llm_router/src/llm_router/ollama.py`) now pins `temperature: 0.0`, the same fix already applied to `match_topic()` for the same documented reason (0008): a judgment-call classification should give the same answer to the same input every time, and it wasn't - a raw one-off comparison outside the eval run got the right answer on a case the eval run itself got wrong, consistent with unseeded sampling noise rather than a capability ceiling.

Everything else below - the actual `superseding` vs. `contradicting` confusion - was investigated at length and **not resolved**. Documented here as a real, load-bearing finding rather than left implicit, so nobody re-runs the same experiments cold later.

## The core finding

Across every real observation gathered (5 true `superseding` cases from a real eval run, 3 hand-reproduced via raw `curl`, plus one deliberately trivial, topic-agnostic sanity check - a meeting time moved from 3pm to 4pm), `llama3.2` **never once produced the word "superseding"**, regardless of prompt wording. It defaults to `contradicting` for anything that reads as a factual change, however mundane.

## What we tried and measured

1. **Reframing the prompt's definitions**, from "logical compatibility" language ("directly conflicts with") to a business-outcome framing ("a normal, expected update, nobody needs to be alerted" vs. "reverses a prior commitment - needs review"), plus one worked example per category (the meeting-time case for `superseding`, the real `contra-04` case for `contradicting`). Result: **no change** - the same two held-out cases (`super-01`, `super-03`) still came back `contradicting`/`corroborating`, even with an explicit worked `superseding` example sitting in the same prompt. This is the same signature as `match_topic()`'s original failure in 0012 (prompt tuning doesn't move a confidently-wrong answer) - so the next thing tried, correctly, was a model swap, not a third prompt rewrite.
2. **Swapping `compare()` to `qwen3.5:4b`** (the same model that fixed `match_topic()` in 0012), keeping the reframed prompt. Result: **no change** - still `contradicting`/`corroborating` on the same two cases. Unlike `match_topic()`, this particular failure is not a model-capability ceiling that a bigger/more careful model clears.
3. **TypeSafe AI's "Jev" (a closed, hosted "decision model" API) and "Kev"** (a same-week, single-author open-weight recreation on Qwen2.5-0.5B, Apache-2.0). Investigated as a structurally different approach - a non-autoregressive classifier returning a full probability distribution across `new`/`corroborating`/`superseding`/`contradicting` instead of one sampled word, which could in principle reveal a close-but-losing `superseding` probability that plain sampling hides entirely. **Parked, not tested against real cases**, by explicit user decision on cost/risk grounds before any accuracy question was even reached: Jev is a closed, paid, third-party cloud API - a real customer-data-handling question (real meeting content going to a new external vendor) as well as a deliberate reversal of `docs/decisions/0010-single-llm-backend-ollama-only.md`'s local-only stance; Kev is a single-author, days-old project requiring its own separate local server process (not another Ollama model), with no track record.
4. **An established, mature open-source alternative: DeBERTa-v3 NLI** (`MoritzLaurer/deberta-v3-base-mnli-fever-anli`, via plain `transformers`, no server, no new network dependency - `scripts/spike_nli_compare.py`). Chosen specifically as the lower-risk alternative to Kev/Jev: years of production use, MIT/Apache-family licensing, no daemon to run. **Real spike result, against the same 4 cases:**

   | case | our label | NLI's answer | confidence |
   |---|---|---|---|
   | `contra-04` | contradicting | contradiction | 99.9% |
   | `super-01` | superseding | **neutral** | 99.9% |
   | `super-03` | superseding | **contradiction** | 81.4% |
   | sanity (meeting time) | superseding | **contradiction** | 95.6% |

   Latency was not a concern (150-270ms/case on CPU, no GPU - faster than `qwen3.5:4b`, comparable to a warm `llama3.2` call). Accuracy was the real result, and it's a clean, informative miss: NLI's `contradiction` label fires whenever two statements simply can't both be literally true at once (3pm vs. 4pm; "one deal" vs. "several deals"; feasible vs. not feasible) - which is exactly the same conflation `llama3.2`/`qwen3.5:4b` were already making, just with a hard number behind it instead of a hunch. It also missed `super-01` in the *other* direction, calling an escalating restatement of the same subject "neutral" (unrelated) entirely.

## Why nothing here worked - the actual conclusion

The `superseding` vs. `contradicting` split, as defined in this system (does a change need a human to review it, or is it a routine update to wave through), is not a linguistic or entailment-level distinction - it's a business judgment about consequence, not about whether two sentences are jointly satisfiable. Every approach tried here - a general chat LLM (two models), a purpose-built decision-model API, and a purpose-built NLI classifier - collapses that judgment back into "did the fact change, yes or no," because that's genuinely what's recoverable from the sentence pair alone, without additional signal (e.g. who said it, what commitment it revises, why the change matters). No amount of further prompt tuning is expected to fix this on its own - the NLI result rules that hypothesis out with a mature, purpose-built classifier, not just another LLM guess.

## Alternatives considered (not yet acted on)

- **Merge `superseding` into `contradicting` operationally** - treat every non-corroborating change as needing human review (`KnowledgeStatus.CONFLICTING`), accepting more review volume in exchange for never silently auto-applying a change that should have been flagged. Cheapest to ship; changes product behavior (more things routed to `pending_review`) - not done unilaterally.
- **Fine-tune on real, outcome-labelled data from this workflow specifically** - the DeBERTa-v3 model card's own stated limitation ("calibration is in-distribution... real calibration needs outcome-labelled data from that workflow") suggests this is plausible in principle, but needs a real labeled dataset that doesn't exist yet - a real project, not a quick fix.
- **A cheap NLI pre-filter for the `new`/`corroborating` split only**, falling back to the existing LLM `compare()` call only on NLI's non-entailment cases. Not pursued further here: `super-01` being misclassified as `neutral` (i.e. "unrelated," not just "some kind of conflict") means this would risk silently dropping a real related-topic update, not just mis-labeling its relationship - a worse failure mode than the one being fixed.

## Revisit when

This is an open product decision, not an engineering one - which of the "Alternatives considered" to pursue (or something else) needs a call from whoever owns the product's tolerance for review volume vs. missed auto-classifications, not a further model swap. Parked at the user's explicit direction (2026-09-27) to move on to other work; nothing here should be read as "solved," and the next person picking this up should start from the table above rather than re-running the same four experiments.

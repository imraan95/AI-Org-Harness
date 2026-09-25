# 0008 — Bridge topic-name drift with an LLM call, not OpenViking's semantic search

**Status:** Accepted
**Date:** 2026-09-25
**Context:** T075 manual PRD §6 walkthrough; follow-up to 0007's own "revisit when real meeting data shows this is a frequent problem" condition.

## Decision

When `get_relevant_knowledge(topic)`'s exact-string match (0007) comes up empty, `context_agent.pipeline._retrieve` does not fall back to OpenViking's own semantic search (`POST /api/v1/search/find`). Instead it fetches the list of existing topic names and asks `llm_router.match_topic()` - a real LLM call - whether any of them is the same real-world subject as the new candidate's topic, worded differently.

`match_topic()` asks this pairwise (one yes/no question per existing topic), not as a single "pick one from this list" prompt, and pins the model's sampling temperature to 0 for this call. Both were empirically necessary, not stylistic choices - see "What we tried and measured" below.

## Why

0007's own exact-match decision predicted this gap and named a semantic-search fallback as the alternative to consider. Real T075 walkthroughs hit it live, twice, with two different drift patterns ("Enterprise SSO" vs "SSO for Enterprise Customers", then "Enterprise SSO" vs "SSO"). We then built and tested the semantic-search fallback for real before rejecting it - see below - and replaced it with a direct LLM call instead.

## What we tried and measured

1. **OpenViking's semantic search (`search/find`), unfiltered.** Two topically-unrelated, months-old fixture records scored ~0.79-0.80 for a query about our brand-new record's actual subject; the new record didn't appear in results at all. Inspecting the returned `abstract` field showed why: OpenViking classifies `.json` files as "code" (not "document") based on file extension, so its VLM-generated summary describes the file's generic JSON *structure* ("a structured data record... no programming-language-specific constructs"), never the actual field values. Since every one of our records has near-identical structure, they all get near-identical summaries - so semantic similarity ends up measuring "how similar is this file's shape", not "how similar is this record's content."
2. **Restricting the search to `level: [2]` (file-content embeddings, bypassing the directory-level abstract).** No change - the file-level embedding for our records is *also* built from the same generic structural summary in this deployment, not raw content as we'd expected from the embedding config.
3. **`processing_mode: "vectors_only"` on write (skips the VLM step entirely, embeds raw file bytes).** Confirmed via the write response (`semantic_status: "skipped"`) that the VLM step was genuinely bypassed - but the new record still didn't surface for a relevant query, while the same two irrelevant old records kept scoring highest. Best explanation: raw, punctuation-heavy JSON text doesn't embed like natural language, so its vector sits far from a plain-English query's vector regardless of actual relevance - while, ironically, even a content-free prose summary scores closer to a natural-language query just by being sentence-shaped.

None of the three are a promising direction to keep tuning - the mismatch is between how we store records (compact JSON) and what this embedding pipeline was built to summarize (documents and code), not a threshold or parameter we happened to pick wrong.

4. **A single LLM call given the whole list of existing topics, asked to pick one or reply "none".** Real Ollama testing (`llama3.2`) found this markedly unreliable - it answered "none" even with the correct match sitting in a 3-item list, on a case it had no trouble with as a single pairwise question.
5. **Pairwise yes/no, one existing topic at a time, default (non-zero) sampling temperature.** The identical yes/no prompt answered "yes" once and "no" on a later run with no other change - non-deterministic, not just occasionally wrong.
6. **Pairwise yes/no, `temperature: 0`.** Reliable across repeated runs - this is what shipped.

## Consequence: OpenViking's role shrinks

This removes the last thing our own code asked OpenViking's semantic layer to do. Its remaining job is a structured file store with exact-match/pattern-match primitives (`glob` for path matching, `grep` for content pattern matching, plain read/write) - a "smart-ish filesystem", not the semantic-searchable store `docs/research/openviking.md` originally proposed using it as. Whether it's still the right storage choice given that narrower role (versus a plain database, especially given its AGPL licensing still awaiting Legal sign-off) is a real open question, not resolved here - logged in build-plan.md's "Open design questions" section rather than acted on now.

## Cost this adds

Retrieve now makes 0 to N extra LLM calls per candidate (N = number of existing distinct topics), but only when the exact match already missed - the common case (a topic that already matches exactly, or one that's genuinely brand new with nothing to check against... actually a brand-new topic still checks against every existing topic once, since there's no way to know it's brand new without checking). At this project's current dev-scale topic count this is negligible; revisit (e.g. a cheaper pre-filter before the pairwise LLM pass) if the number of distinct topics grows enough for this to matter.

## Alternatives considered

- **Write a parallel plain-English copy of each fact, purely for OpenViking to summarize/search** (keeping the strict JSON as the source of truth our own code reads/writes). Not ruled out for the future, but not attempted here: it would very likely get a more content-aware summary from OpenViking's document path, but doesn't by itself prove the embedding-similarity-vs-plain-English-query mismatch from finding 3 above is solved, and doubles what's written per fact.
- **Canonicalizing topic strings** (already named as rejected-for-now in 0007, for the same "more moving parts than the MVP needs" reason).

## Revisit when

The number of distinct topics grows large enough that a pairwise LLM check against every existing topic on every exact-match miss becomes a real latency/cost problem - at that point, a cheap pre-filter (e.g. a fast fuzzy-string or keyword narrowing pass before the LLM call) is the first thing to try, not going back to embeddings.

# decisions

Lightweight ADRs (architecture decision records) as the system evolves.

- [0001 — Tech stack: Next.js + Supabase + FastAPI/Python](0001-tech-stack.md)
- [0002 — OpenViking as a forked, separately-deployed service, part of MVP from day one](0002-openviking-forked-service.md)
- [0003 — OpenViking's storage model, and how we integrate with it](0003-openviking-storage-and-integration-model.md)
- [0004 — AI model strategy: open-weight default, swappable via a router](0004-ai-model-strategy.md)
- [0005 — Confidence scoring is a rules/lookup table, not ML](0005-confidence-scoring-rules-not-ml.md)
- [0006 — Human-in-the-loop gating for high-impact knowledge writes](0006-human-in-the-loop-review-gating.md)
- [0007 — Topic retrieval: exact match now, evaluate semantic fallback later](0007-topic-retrieval-exact-match.md)
- [0008 — Bridge topic-name drift with an LLM call, not OpenViking's semantic search](0008-topic-matching-via-llm-not-openviking-semantic-search.md)
- [0009 — Postgres replaces OpenViking as the default knowledge storage layer](0009-postgres-replaces-openviking-as-default-storage.md)

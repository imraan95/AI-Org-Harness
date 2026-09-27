"""Throwaway spike - NOT part of the pipeline.

Question being tested: can an established, off-the-shelf open-source NLI
(natural language inference) checkpoint classify our real compare()
cases, and is it fast enough to not add latency versus the current
Ollama-based compare() call?

This is deliberately NOT another from-scratch/days-old decision model
(that's what we just parked with Kev) - DeBERTa-v3 NLI checkpoints have
years of production use, are MIT/Apache licensed, and run as a plain
`transformers` forward pass (no server, no daemon, no new network
dependency).

Run directly, without touching this project's own dependencies:

    uv run --with transformers --with torch python scripts/spike_nli_compare.py

NLI only ever answers entailment / neutral / contradiction - it has no
concept of our specific "superseding" (expected update, don't flag) vs.
"contradicting" (reversal, flag for review) distinction. So this script
is checking a narrower, more realistic question than "does this replace
compare()": can NLI reliably separate new/corroborating from
"something changed" fast and for free, leaving only the harder
superseding-vs-contradicting split to the existing LLM call - on a
smaller slice of cases, not all of them.
"""

from __future__ import annotations

import time

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Base size chosen for latency: ~184M params, single forward pass, no
# decoding loop. MoritzLaurer/deberta-v3-xsmall-mnli-fever-anli (~70M
# params) is a drop-in swap here if base still isn't fast enough.
MODEL_NAME = "MoritzLaurer/deberta-v3-base-mnli-fever-anli"

# The same real cases used throughout this session's compare()
# investigation, so results are directly comparable to what we already
# measured for llama3.2/qwen3.5:4b.
CASES = [
    {
        "id": "super-01",
        "existing": "SSO is an occasional customer request.",
        "candidate": (
            "Three enterprise customers have asked for SSO this quarter "
            "and Sales considers it a potential deal blocker."
        ),
        "our_expected_label": "superseding",
    },
    {
        "id": "super-03",
        "existing": "GDS connectivity is blocking one enterprise hotel group deal.",
        "candidate": (
            "Two more enterprise prospects this month named Sabre and "
            "Amadeus integration specifically as a signing condition - GDS "
            "connectivity has gone from a one-off blocker to a recurring "
            "theme across deals."
        ),
        "our_expected_label": "superseding",
    },
    {
        "id": "contra-04",
        "existing": (
            "Engineering said GDS connectivity is technically feasible "
            "within the current architecture."
        ),
        "candidate": (
            "Engineering now says GDS connectivity would require a full "
            "rebuild of the reservations core and is not feasible within "
            "the current architecture."
        ),
        "our_expected_label": "contradicting",
    },
    {
        "id": "sanity-meeting-time",
        "existing": "The team meeting is scheduled for 3pm on Thursday.",
        "candidate": "The team meeting has been moved to 4pm on Thursday.",
        "our_expected_label": "superseding",
    },
]


def main() -> None:
    print(f"Loading {MODEL_NAME} ...")
    load_start = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()
    load_seconds = time.monotonic() - load_start
    print(
        f"Loaded in {load_seconds:.2f}s - this is a ONE-TIME cost paid "
        "once per worker process lifetime (like Ollama keeping a model "
        "warm), not per-call. Only the per-case numbers below are the "
        "real per-call latency to compare against compare()'s current "
        "Ollama call.\n"
    )

    # Read the label order from the checkpoint's own config rather than
    # assuming it - this varies between NLI checkpoints and guessing
    # wrong here would silently invert every result.
    id2label = model.config.id2label
    print(f"Label mapping (from the checkpoint's own config): {id2label}\n")

    for case in CASES:
        # NLI convention: premise = what we already believe (existing),
        # hypothesis = the new incoming claim (candidate). Direction
        # matters - swapping these would ask a different question.
        inputs = tokenizer(
            case["existing"], case["candidate"], return_tensors="pt", truncation=True
        )
        start = time.monotonic()
        with torch.no_grad():
            logits = model(**inputs).logits
        elapsed_ms = (time.monotonic() - start) * 1000
        probs = torch.softmax(logits, dim=-1)[0]
        ranked = sorted(
            ((id2label[i], float(probs[i])) for i in range(len(probs))),
            key=lambda item: -item[1],
        )
        print(f"[{case['id']}] our label: {case['our_expected_label']}")
        print(f"  existing:  {case['existing']}")
        print(f"  candidate: {case['candidate']}")
        print(f"  NLI says:  {ranked}")
        print(f"  latency:   {elapsed_ms:.1f}ms\n")


if __name__ == "__main__":
    main()

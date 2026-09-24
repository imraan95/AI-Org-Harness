from __future__ import annotations

# Confidence scoring per PRD §10: rules, not ML. Each entry is a *source
# context* - what kind of statement this was - mapped to a numeric score.
# The PRD's own example table:
#   CEO-approved decision        High
#   Formal roadmap decision      High
#   PM statement                 Medium
#   Customer statement           Medium
#   Speculation                  Low
#   Casual conversation          Low
CONFIDENCE_BY_SOURCE_CONTEXT: dict[str, float] = {
    "ceo_approved_decision": 0.9,
    "formal_roadmap_decision": 0.9,
    "pm_statement": 0.6,
    "customer_statement": 0.6,
    "speculation": 0.3,
    "casual_conversation": 0.3,
}

DEFAULT_CONFIDENCE = CONFIDENCE_BY_SOURCE_CONTEXT["casual_conversation"]


def score_confidence(source_context: str) -> float:
    """Return a 0-1 confidence score for a given source context."""
    return CONFIDENCE_BY_SOURCE_CONTEXT.get(source_context, DEFAULT_CONFIDENCE)


def confidence_bucket(confidence: float) -> str:
    """Bucket a numeric confidence score into high/medium/low."""
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"

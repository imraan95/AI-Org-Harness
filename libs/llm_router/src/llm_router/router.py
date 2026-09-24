from __future__ import annotations

import os

# Which model *tier* handles each task, per PRD §11's "cheapest capable
# model" principle. Tiers are resolved to an actual model id by
# TIER_TO_MODEL below, both overridable via env vars.
DEFAULT_TASK_TIERS: dict[str, str] = {
    "generate": "small",
    "extract": "small",
    "classify": "small",
    "compare": "large",
    "summarise": "small",
}

DEFAULT_TIER_TO_MODEL: dict[str, str] = {
    "small": "llama3.2",
    "large": "llama3.1:70b",
}


def get_model_for(task: str) -> str:
    """Return the model id configured to handle `task`.

    Override a single task's tier with an env var named
    `LLM_TASK_<TASK>_TIER` (e.g. `LLM_TASK_COMPARE_TIER=small`), or override
    what a tier resolves to with `LLM_TIER_<TIER>_MODEL`
    (e.g. `LLM_TIER_LARGE_MODEL=llama3.1:8b`).
    """
    if task not in DEFAULT_TASK_TIERS:
        raise ValueError(f"Unknown task: {task!r}")

    tier = os.environ.get(
        f"LLM_TASK_{task.upper()}_TIER", DEFAULT_TASK_TIERS[task]
    )
    return os.environ.get(
        f"LLM_TIER_{tier.upper()}_MODEL", DEFAULT_TIER_TO_MODEL.get(tier, tier)
    )

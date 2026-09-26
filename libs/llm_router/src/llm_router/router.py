from __future__ import annotations

from .interface import LLM
from .ollama import OllamaLLM


def get_llm() -> LLM:
    """Return the configured LLM backend.

    Per docs/decisions/0010-single-llm-backend-ollama-only.md: Ollama is the
    only supported backend, so this always returns `OllamaLLM()` - no
    per-provider branching, no per-task model tiering (OllamaLLM already
    uses one model, from `OLLAMA_MODEL`, for every task).

    This function is still the one seam every call site should go through
    rather than constructing `OllamaLLM()` directly - if a different
    backend is ever wanted, this is the only place that needs to change.
    """
    return OllamaLLM()

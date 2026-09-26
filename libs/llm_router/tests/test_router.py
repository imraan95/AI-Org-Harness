from llm_router import OllamaLLM, get_llm


def test_get_llm_returns_ollama():
    # Per docs/decisions/0010-single-llm-backend-ollama-only.md: Ollama is
    # the only supported backend - no branching, no api-key check.
    assert isinstance(get_llm(), OllamaLLM)

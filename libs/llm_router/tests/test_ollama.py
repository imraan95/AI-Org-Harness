import httpx
import pytest

from llm_router.ollama import DEFAULT_OLLAMA_BASE_URL, OllamaLLM


def _ollama_available() -> bool:
    try:
        response = httpx.get(f"{DEFAULT_OLLAMA_BASE_URL}/api/tags", timeout=1.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_available(), reason="Ollama is not running locally"
)


async def test_extract_returns_expected_fields():
    llm = OllamaLLM()
    result = await llm.extract(
        "Alice: Three enterprise customers have asked for SSO this quarter."
    )
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "topic" in result[0]
    assert "statement" in result[0]


async def test_classify_returns_one_of_the_given_categories():
    llm = OllamaLLM()
    result = await llm.classify(
        "We decided to ship SSO in November.",
        ["decision", "fact", "hypothesis"],
    )
    assert result in ["decision", "fact", "hypothesis"]


async def test_compare_returns_one_of_the_four_relationships():
    llm = OllamaLLM()
    result = await llm.compare(
        {"topic": "Enterprise SSO", "statement": "We're going to ship SSO in November."},
        [{"statement": "SSO is not planned for Q4."}],
    )
    assert result in ["new", "corroborating", "superseding", "contradicting"]


async def test_embed_returns_a_nonempty_vector_of_floats():
    llm = OllamaLLM()
    result = await llm.embed("Three enterprise customers have asked for SSO.")
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(value, float) for value in result)


async def test_embed_is_deterministic_for_the_same_text():
    llm = OllamaLLM()
    first = await llm.embed("Three enterprise customers have asked for SSO.")
    second = await llm.embed("Three enterprise customers have asked for SSO.")
    assert first == second

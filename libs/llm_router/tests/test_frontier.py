import httpx

from llm_router import FrontierLLM, OllamaLLM, get_llm


def test_get_llm_falls_back_to_ollama_when_no_api_key_set(monkeypatch):
    monkeypatch.delenv("FRONTIER_API_KEY", raising=False)
    llm = get_llm()
    assert isinstance(llm, OllamaLLM)


def test_get_llm_selects_frontier_backend_when_api_key_set(monkeypatch):
    monkeypatch.setenv("FRONTIER_API_KEY", "fake-key-for-test")
    llm = get_llm()
    assert isinstance(llm, FrontierLLM)


async def test_frontier_llm_generate_calls_the_configured_api_and_parses_response(
    monkeypatch,
):
    class _FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"content": [{"text": "mocked response"}]}

    async def fake_post(self, url, json):
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    llm = FrontierLLM(api_key="fake-key-for-test")
    result = await llm.generate("hello")

    assert result == "mocked response"

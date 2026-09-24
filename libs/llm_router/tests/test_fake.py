from llm_router import FakeLLM


async def test_fake_llm_returns_configured_canned_responses():
    fake = FakeLLM()
    fake.set_next_generate_result("generated text")
    fake.set_next_extract_result([{"topic": "sso"}])
    fake.set_next_classify_result("decision")
    fake.set_next_compare_result("contradicts")
    fake.set_next_summarise_result("a summary")
    fake.set_next_embed_result([0.1, 0.2, 0.3])

    assert await fake.generate("prompt") == "generated text"
    assert await fake.extract("text") == [{"topic": "sso"}]
    assert await fake.classify("text", ["decision", "fact"]) == "decision"
    assert await fake.compare({}, []) == "contradicts"
    assert await fake.summarise("text") == "a summary"
    assert await fake.embed("text") == [0.1, 0.2, 0.3]
    assert fake.embed_calls == ["text"]

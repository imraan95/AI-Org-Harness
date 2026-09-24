import pytest

from llm_router import LLM


class _MinimalLLM(LLM):
    async def generate(self, prompt):
        return ""

    async def extract(self, text):
        return []

    async def classify(self, text, categories):
        return categories[0]

    async def compare(self, candidate, existing):
        return "new"

    async def summarise(self, text):
        return ""

    async def embed(self, text):
        return []


def test_subclass_implementing_all_methods_can_be_instantiated():
    instance = _MinimalLLM()
    assert isinstance(instance, LLM)


def test_subclass_missing_a_method_cannot_be_instantiated():
    class _Incomplete(LLM):
        async def generate(self, prompt):
            return ""

        async def extract(self, text):
            return []

        async def classify(self, text, categories):
            return categories[0]

        async def compare(self, candidate, existing):
            return "new"

        # summarise intentionally omitted

    with pytest.raises(TypeError):
        _Incomplete()

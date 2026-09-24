from .fake import FakeLLM
from .frontier import FrontierLLM
from .interface import LLM
from .ollama import OllamaLLM
from .router import get_llm, get_model_for

__all__ = [
    "LLM",
    "FakeLLM",
    "OllamaLLM",
    "FrontierLLM",
    "get_model_for",
    "get_llm",
]

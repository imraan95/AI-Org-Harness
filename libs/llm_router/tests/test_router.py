import pytest

from llm_router import get_model_for


def test_compare_defaults_to_the_configured_large_model():
    assert get_model_for("compare") == "llama3.1:70b"


def test_extract_defaults_to_the_configured_small_model():
    assert get_model_for("extract") == "llama3.2"


def test_tier_is_overridable_via_env_var(monkeypatch):
    monkeypatch.setenv("LLM_TASK_COMPARE_TIER", "small")
    assert get_model_for("compare") == "llama3.2"


def test_model_for_a_tier_is_overridable_via_env_var(monkeypatch):
    monkeypatch.setenv("LLM_TIER_LARGE_MODEL", "some-other-model")
    assert get_model_for("compare") == "some-other-model"


def test_unknown_task_raises_value_error():
    with pytest.raises(ValueError):
        get_model_for("not_a_real_task")

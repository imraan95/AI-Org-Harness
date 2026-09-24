import pytest

from context_agent.confidence import confidence_bucket, score_confidence


@pytest.mark.parametrize(
    "source_context,expected_bucket",
    [
        ("ceo_approved_decision", "high"),
        ("formal_roadmap_decision", "high"),
        ("pm_statement", "medium"),
        ("customer_statement", "medium"),
        ("speculation", "low"),
        ("casual_conversation", "low"),
    ],
)
def test_confidence_bucket_matches_prd_examples(source_context, expected_bucket):
    score = score_confidence(source_context)
    assert confidence_bucket(score) == expected_bucket


def test_unknown_source_context_defaults_to_low():
    score = score_confidence("something_unrecognised")
    assert confidence_bucket(score) == "low"

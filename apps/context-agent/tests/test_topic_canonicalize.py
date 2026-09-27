import pytest

from context_agent.topic_canonicalize import canonicalize_topic, normalize_topic_key


@pytest.mark.parametrize(
    "topic,expected",
    [
        ("GDS connectivity", "gds_connectivity"),
        ("gds_connectivity", "gds_connectivity"),
        ("GDS-Connectivity!", "gds_connectivity"),
        ("  Dynamic   Pricing Rules  ", "dynamic_pricing_rules"),
    ],
)
def test_normalize_topic_key_collapses_formatting_variants(topic, expected):
    assert normalize_topic_key(topic) == expected


def test_exact_formatting_variant_is_caught():
    # This is the real, measured failure case from the eval harness:
    # match_topic() was asked to bridge these and got it wrong more than
    # once - this function should catch it for free, before match_topic()
    # is ever called.
    assert (
        canonicalize_topic("GDS connectivity", ["gds_connectivity"])
        == "gds_connectivity"
    )


def test_token_overlap_catches_a_near_miss_variant():
    assert (
        canonicalize_topic("Dynamic Pricing Rules", ["dynamic_pricing_rule"])
        == "dynamic_pricing_rule"
    )


def test_genuinely_unrelated_topic_is_not_matched():
    # The real near-miss case from the eval harness that fooled the LLM
    # itself (match_topic() confidently said "yes" to this exact pair) -
    # no shared tokens here at all, so this must stay a clean non-match.
    assert (
        canonicalize_topic("Mobile push notifications", ["enterprise_sso"]) is None
    )


def test_genuine_paraphrase_sharing_real_tokens_is_matched():
    # This function isn't only a formatting safety net - a paraphrase that
    # still shares substantial, non-generic words ("enterprise", "sso") is
    # a legitimate, conservative match, and a bonus: one fewer case that
    # needs match_topic()'s LLM judgment at all. PRD's own worked example.
    assert (
        canonicalize_topic("SSO for Enterprise Customers", ["enterprise_sso"])
        == "enterprise_sso"
    )


def test_unrelated_topics_sharing_only_generic_words_are_not_matched():
    assert (
        canonicalize_topic("General status update", ["general_team_notes"]) is None
    )


def test_empty_existing_topics_returns_none():
    assert canonicalize_topic("Anything", []) is None


def test_empty_candidate_topic_returns_none():
    assert canonicalize_topic("", ["gds_connectivity"]) is None


# The four cases below are the real near_miss_non_match scenarios from the
# eval harness (deceptively similar surface wording, genuinely different
# subjects) - a first version of this function's token-overlap check (any
# single shared non-generic token) wrongly matched several of these, since
# one shared word like "dynamic" or "mobile" isn't real evidence on its own.
# Requiring at least two matched tokens (_MIN_MATCHED_TOKENS) fixed all four.
def test_shared_single_word_dynamic_does_not_cause_a_false_match():
    assert (
        canonicalize_topic(
            "Dynamic currency conversion", ["dynamic_pricing_rules"]
        )
        is None
    )


def test_shared_single_word_mobile_does_not_cause_a_false_match():
    assert (
        canonicalize_topic("Maintenance mobile app", ["housekeeping_mobile_app"])
        is None
    )


def test_shared_single_word_messaging_does_not_cause_a_false_match():
    assert (
        canonicalize_topic(
            "Internal messaging for shift handovers",
            ["guest_messaging_automation"],
        )
        is None
    )


def test_unrelated_gds_and_seo_topics_are_not_matched():
    assert (
        canonicalize_topic(
            "Google Business Profile SEO listing", ["gds_connectivity"]
        )
        is None
    )

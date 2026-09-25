"""T064: `format_answer()` against PRD §15's structure - "Current
understanding", "Evidence:", and a tension sentence when records conflict.
Pure unit tests, no external services needed.
"""

from __future__ import annotations

from mcp_server.formatting import format_answer, format_history


def test_format_answer_has_understanding_and_evidence_sections():
    records = [
        {
            "id": "K-1",
            "topic": "enterprise_sso",
            "statement": "SSO has been identified as a recurring enterprise customer requirement.",
            "status": "active",
            "source_ids": ["m1", "m2", "m3"],
        }
    ]

    answer = format_answer(records)

    assert answer.startswith("Current understanding:")
    assert "SSO has been identified as a recurring enterprise customer requirement." in answer
    assert "Evidence:" in answer
    assert "enterprise_sso: 3 sources" in answer


def test_format_answer_includes_a_tension_sentence_for_conflicting_records():
    records = [
        {
            "id": "K-1",
            "topic": "enterprise_sso",
            "statement": "SSO has been identified as a recurring enterprise customer requirement.",
            "status": "active",
            "source_ids": ["m1"],
        },
        {
            "id": "K-2",
            "topic": "enterprise_sso",
            "statement": "The latest product decision prioritised onboarding improvements over SSO.",
            "status": "conflicting",
            "conflicts_with": ["K-1"],
            "source_ids": ["m4"],
        },
    ]

    answer = format_answer(records)

    assert "Current understanding:" in answer
    assert "Evidence:" in answer
    assert "tension" in answer
    assert "enterprise_sso" in answer.split("tension", 1)[1]


def test_format_answer_uses_real_sources_when_present():
    records = [
        {
            "id": "K-1",
            "topic": "enterprise_sso",
            "statement": "Three enterprise customers have asked for SSO.",
            "status": "active",
            "source_ids": ["m1"],
            "sources": [{"meeting_title": "Customer call with Acme", "meeting_date": "2026-01-01"}],
        }
    ]

    answer = format_answer(records)

    assert "- Customer call with Acme" in answer


def test_format_answer_includes_each_records_id_so_it_can_be_looked_up_later():
    """A summary answer with no id in it is a dead end for an agent - it
    can't follow up with get_evidence/get_knowledge_history on anything it
    just surfaced. Confirmed missing live (a Claude Desktop chat guessed
    at ids and got guaranteed 404s) before this test/fix existed."""
    records = [
        {
            "id": "K-abc123",
            "topic": "enterprise_sso",
            "statement": "SSO has been identified as a recurring enterprise customer requirement.",
            "status": "active",
            "source_ids": ["m1", "m2", "m3"],
        }
    ]

    answer = format_answer(records)

    assert "K-abc123" in answer


def test_format_answer_includes_the_id_alongside_real_sources_too():
    records = [
        {
            "id": "K-abc123",
            "topic": "enterprise_sso",
            "statement": "Three enterprise customers have asked for SSO.",
            "status": "active",
            "source_ids": ["m1"],
            "sources": [{"meeting_title": "Customer call with Acme", "meeting_date": "2026-01-01"}],
        }
    ]

    answer = format_answer(records)

    assert "- Customer call with Acme" in answer
    assert "K-abc123" in answer


def test_format_answer_handles_no_records():
    answer = format_answer([])

    assert "Current understanding:" in answer
    assert "Evidence:" in answer


def test_format_history_lists_newest_to_oldest_with_status_labels():
    records = [
        {
            "id": "K-new",
            "statement": "SSO is now a recurring, escalating customer request.",
            "status": "active",
            "last_updated_at": "2026-09-25T00:00:00Z",
        },
        {
            "id": "K-old",
            "statement": "SSO is an occasional customer request.",
            "status": "superseded",
            "superseded_at": "2026-09-25T00:00:00Z",
        },
    ]

    answer = format_history(records)

    assert answer.startswith("History (newest to oldest):")
    assert "1. [ACTIVE]" in answer
    assert "SSO is now a recurring, escalating customer request." in answer
    assert "2. [SUPERSEDED]" in answer
    assert "SSO is an occasional customer request." in answer
    # The new record's line should come before the old one's.
    assert answer.index("SSO is now") < answer.index("SSO is an occasional")


def test_format_history_handles_no_records():
    answer = format_history([])

    assert answer == "No history recorded for this knowledge."

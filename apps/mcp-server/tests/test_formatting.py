"""T064: `format_answer()` against PRD §15's structure - "Current
understanding", "Evidence:", and a tension sentence when records conflict.
Pure unit tests, no external services needed.
"""

from __future__ import annotations

from mcp_server.formatting import format_answer


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


def test_format_answer_handles_no_records():
    answer = format_answer([])

    assert "Current understanding:" in answer
    assert "Evidence:" in answer

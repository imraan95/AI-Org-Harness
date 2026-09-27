"""Labeled evaluation cases for context-agent's Extract/Retrieve/Compare
pipeline - ground truth for measuring topic-matching accuracy, relationship
(new/corroborating/superseding/contradicting) accuracy, and extraction
recall ("information gain"), against the REAL pipeline (real Ollama, real
Postgres knowledge store) rather than FakeLLM fixtures.

This file is data only - no pipeline calls, no assertions. The scoring
script that runs these cases through process_transcript() and reports
metrics is a separate, later piece (not built yet - see the conversation
that led to this file for why: get real numbers on our own pipeline
before considering any third-party memory library).

Every scenario here is synthetic/invented for testing - none of it
describes real RMS product decisions, customers, or roadmap.

Categories, and what each is designed to catch:
  - "new": no existing knowledge on the topic. Retrieve should find
    nothing, Compare should short-circuit to "new" without an LLM call
    (pipeline.py's own documented shortcut).
  - "corroborating": restates/reinforces existing knowledge, same or
    near-identical topic wording. Should NOT create a duplicate belief.
  - "superseding": a genuine update to an existing belief. Several of
    these deliberately use DRIFTED topic wording (a different string for
    the same real-world subject) to exercise match_topic() (0008) - the
    exact case 0008 was built to bridge - not just the exact-match path.
  - "contradicting": a genuine reversal, same topic wording (drift is
    deliberately NOT mixed in here, to isolate relationship-classification
    accuracy from topic-matching accuracy - T076 already found mixing
    both in one case makes failures ambiguous to diagnose).
  - "near_miss_non_match": an existing topic that is superficially
    similar (shared vocabulary/domain) but is NOT the same real-world
    subject. match_topic() must correctly return None here - this
    category exists because nothing today measures match_topic()'s
    FALSE POSITIVE rate (over-eager bridging), only its true-positive
    rate on genuine drift.

`expected_fact_keywords` is a loose, lowercase substring check against
whatever extract() actually produces (joined topic + statement text) -
not an exact-match check, since LLM output paraphrases. Used to measure
how much of a transcript's real content actually gets surfaced as a
candidate at all (extraction recall / "information gain"), independent
of whether the relationship/topic-matching afterward is correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Relationship = Literal["new", "corroborating", "superseding", "contradicting"]


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: Literal[
        "new", "corroborating", "superseding", "contradicting", "near_miss_non_match"
    ]
    # None for "new" cases - nothing pre-seeded.
    existing_topic: str | None
    existing_statement: str | None
    transcript_text: str
    # For "new" and "near_miss_non_match": None (nothing should match).
    expected_matched_topic: str | None
    expected_relationship: Relationship
    expected_fact_keywords: list[str]
    notes: str


EVAL_CASES: list[EvalCase] = [
    # ---- new: no existing knowledge --------------------------------
    EvalCase(
        id="new-01-dynamic-pricing",
        category="new",
        existing_topic=None,
        existing_statement=None,
        transcript_text=(
            "Priya: Product team decided to ship rule-based dynamic pricing "
            "in Q1, so properties can auto-adjust nightly rates based on "
            "occupancy."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["dynamic pricing", "q1"],
        notes="Single clear new fact, no ambiguity.",
    ),
    EvalCase(
        id="new-02-housekeeping-app",
        category="new",
        existing_topic=None,
        existing_statement=None,
        transcript_text=(
            "Jordan: Support raised that three mid-size caravan park "
            "customers have asked for a housekeeping mobile app to mark "
            "rooms clean or dirty in real time."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["housekeeping", "mobile app"],
        notes="Customer-insight-shaped fact.",
    ),
    EvalCase(
        id="new-03-gds-connectivity",
        category="new",
        existing_topic=None,
        existing_statement=None,
        transcript_text=(
            "Sam: Sales flagged that a large hotel group prospect requires "
            "GDS connectivity - Sabre and Amadeus specifically - before "
            "they'll sign, and we don't currently support it."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["gds", "sabre"],
        notes="Deal-blocker-shaped fact with two named systems - tests whether extract() keeps both or drops one.",
    ),
    EvalCase(
        id="new-04-guest-messaging",
        category="new",
        existing_topic=None,
        existing_statement=None,
        transcript_text=(
            "Alex: Leadership approved automated guest messaging templates "
            "- pre-arrival and post-checkout - as a Q2 roadmap item."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["guest messaging", "q2"],
        notes="Decision-shaped fact.",
    ),
    EvalCase(
        id="new-05-multi-currency",
        category="new",
        existing_topic=None,
        existing_statement=None,
        transcript_text=(
            "Priya: Finance noted that two European resort customers are "
            "asking for multi-currency invoicing, which the billing module "
            "doesn't support yet."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["multi-currency", "invoicing"],
        notes="Customer-insight-shaped fact naming a specific count/segment.",
    ),
    # ---- corroborating: restates existing knowledge -----------------
    EvalCase(
        id="corr-01-dynamic-pricing",
        category="corroborating",
        existing_topic="dynamic_pricing_rules",
        existing_statement=(
            "Product team decided to ship rule-based dynamic pricing in Q1."
        ),
        transcript_text=(
            "Jordan: Another product sync confirmed dynamic pricing rules "
            "are still targeted for Q1, no change to scope."
        ),
        expected_matched_topic="dynamic_pricing_rules",
        expected_relationship="corroborating",
        expected_fact_keywords=["dynamic pricing", "q1"],
        notes="Same topic, reaffirms rather than changes the belief.",
    ),
    EvalCase(
        id="corr-02-gds-connectivity",
        category="corroborating",
        existing_topic="gds_connectivity",
        existing_statement=(
            "Sales flagged GDS connectivity as a blocker for one large "
            "hotel group prospect."
        ),
        transcript_text=(
            "Sam: In today's pipeline review, GDS connectivity kept coming "
            "up again as a blocker with enterprise hotel prospects."
        ),
        expected_matched_topic="gds_connectivity",
        expected_relationship="corroborating",
        expected_fact_keywords=["gds", "blocker"],
        notes="Reinforces without adding a new count or reversing anything.",
    ),
    EvalCase(
        id="corr-03-housekeeping-app",
        category="corroborating",
        existing_topic="housekeeping_mobile_app",
        existing_statement=(
            "Support raised that three caravan park customers want a "
            "housekeeping mobile app."
        ),
        transcript_text=(
            "Alex: Customer success said two more caravan park customers "
            "this week also asked about a mobile housekeeping app."
        ),
        expected_matched_topic="housekeeping_mobile_app",
        expected_relationship="corroborating",
        expected_fact_keywords=["housekeeping", "caravan"],
        notes="Deliberately borderline vs. superseding - the count changed (three -> more), but this is corroboration of an ongoing pattern, not a reversal. A model calling this 'superseding' instead isn't unreasonable; worth watching in results rather than treating as an obvious failure.",
    ),
    EvalCase(
        id="corr-04-guest-messaging",
        category="corroborating",
        existing_topic="guest_messaging_automation",
        existing_statement=(
            "Leadership approved automated guest messaging templates for Q2."
        ),
        transcript_text=(
            "Priya: Today's planning meeting reconfirmed automated guest "
            "messaging templates remain scheduled for Q2."
        ),
        expected_matched_topic="guest_messaging_automation",
        expected_relationship="corroborating",
        expected_fact_keywords=["guest messaging", "q2"],
        notes="Clean reaffirmation, no change.",
    ),
    # ---- superseding: genuine updates, several with topic drift -----
    EvalCase(
        id="super-01-sso-topic-drift",
        category="superseding",
        existing_topic="enterprise_sso",
        existing_statement="SSO is an occasional customer request.",
        transcript_text=(
            "Sam: Three enterprise customers have asked for SSO this "
            "quarter and Sales considers it a potential deal blocker."
        ),
        expected_matched_topic="enterprise_sso",
        expected_relationship="superseding",
        expected_fact_keywords=["sso", "enterprise"],
        notes="PRD §6's own worked example. New candidate's topic will very likely be worded differently ('SSO for enterprise customers' or similar) - this is the primary case exercising match_topic()/0008, not just the exact-match path.",
    ),
    EvalCase(
        id="super-02-dynamic-pricing-exact-topic",
        category="superseding",
        existing_topic="dynamic_pricing_rules",
        existing_statement=(
            "Product team decided to ship rule-based dynamic pricing in Q1."
        ),
        transcript_text=(
            "Jordan: Product pushed dynamic pricing rules from Q1 to Q2 "
            "due to a resourcing conflict with the channel manager rebuild."
        ),
        expected_matched_topic="dynamic_pricing_rules",
        expected_relationship="superseding",
        expected_fact_keywords=["dynamic pricing", "q2"],
        notes="Same topic wording expected (no drift) - isolates relationship-classification accuracy from topic-matching accuracy.",
    ),
    EvalCase(
        id="super-03-gds-topic-drift",
        category="superseding",
        existing_topic="gds_connectivity",
        existing_statement=(
            "GDS connectivity is blocking one enterprise hotel group deal."
        ),
        transcript_text=(
            "Sam: Two more enterprise prospects this month named Sabre and "
            "Amadeus integration specifically as a signing condition - GDS "
            "connectivity has gone from a one-off blocker to a recurring "
            "theme across deals."
        ),
        expected_matched_topic="gds_connectivity",
        expected_relationship="superseding",
        expected_fact_keywords=["gds", "sabre"],
        notes="Drifted topic wording likely (e.g. 'Sabre/Amadeus integration') plus a real change in scope (one deal -> recurring theme).",
    ),
    EvalCase(
        id="super-04-multi-currency-topic-drift",
        category="superseding",
        existing_topic="multi_currency_billing",
        existing_statement=(
            "Two European resort customers are asking for multi-currency "
            "invoicing."
        ),
        transcript_text=(
            "Priya: Finance now counts five customers across three regions "
            "requesting multi-currency invoicing, no longer just the two "
            "European resorts."
        ),
        expected_matched_topic="multi_currency_billing",
        expected_relationship="superseding",
        expected_fact_keywords=["multi-currency", "five"],
        notes="Drifted topic wording likely, plus an explicit scope change (2 -> 5, one region -> three).",
    ),
    EvalCase(
        id="super-05-guest-messaging-exact-topic",
        category="superseding",
        existing_topic="guest_messaging_automation",
        existing_statement=(
            "Leadership approved automated guest messaging templates for Q2."
        ),
        transcript_text=(
            "Alex: Leadership moved automated guest messaging templates up "
            "to Q1 after a customer escalation."
        ),
        expected_matched_topic="guest_messaging_automation",
        expected_relationship="superseding",
        expected_fact_keywords=["guest messaging", "q1"],
        notes="Same topic wording expected - a schedule reversal (Q2 -> Q1), not a drift case.",
    ),
    # ---- contradicting: genuine reversals, exact topic wording ------
    EvalCase(
        id="contra-01-sso-prd-example",
        category="contradicting",
        existing_topic="enterprise_sso",
        existing_statement="SSO is not planned for this quarter.",
        transcript_text=(
            "Alex: Leadership confirmed today that we're shipping SSO in "
            "November."
        ),
        expected_matched_topic="enterprise_sso",
        expected_relationship="contradicting",
        expected_fact_keywords=["sso", "november"],
        notes="PRD §9's own worked example. Exact topic wording used deliberately (T076 found mixing topic-drift and contradiction in one case makes failures hard to diagnose - which part broke).",
    ),
    EvalCase(
        id="contra-02-dynamic-pricing-reversal",
        category="contradicting",
        existing_topic="dynamic_pricing_rules",
        existing_statement=(
            "Product decided dynamic pricing rules will NOT auto-adjust "
            "rates without manager approval, to avoid pricing errors."
        ),
        transcript_text=(
            "Jordan: Product changed direction - dynamic pricing rules "
            "should auto-adjust rates without requiring manager approval, "
            "to move faster."
        ),
        expected_matched_topic="dynamic_pricing_rules",
        expected_relationship="contradicting",
        expected_fact_keywords=["dynamic pricing", "approval"],
        notes="Direct policy reversal on the same specific mechanism (manager approval requirement).",
    ),
    EvalCase(
        id="contra-03-housekeeping-pricing-reversal",
        category="contradicting",
        existing_topic="housekeeping_mobile_app",
        existing_statement=(
            "Support committed the housekeeping mobile app will be "
            "included free for all existing customers."
        ),
        transcript_text=(
            "Priya: Product clarified the housekeeping mobile app will "
            "actually be a paid add-on, not included free for existing "
            "customers."
        ),
        expected_matched_topic="housekeeping_mobile_app",
        expected_relationship="contradicting",
        expected_fact_keywords=["housekeeping", "paid"],
        notes="Commercial-terms reversal (free -> paid) - a case where getting this wrong (e.g. calling it 'superseding') has real business consequence if surfaced to a customer-facing team.",
    ),
    EvalCase(
        id="contra-04-gds-feasibility-reversal",
        category="contradicting",
        existing_topic="gds_connectivity",
        existing_statement=(
            "Engineering said GDS connectivity is technically feasible "
            "within the current architecture."
        ),
        transcript_text=(
            "Sam: Engineering now says GDS connectivity would require a "
            "full rebuild of the reservations core and is not feasible "
            "within the current architecture."
        ),
        expected_matched_topic="gds_connectivity",
        expected_relationship="contradicting",
        expected_fact_keywords=["gds", "feasible"],
        notes="Technical-feasibility reversal.",
    ),
    # ---- near_miss_non_match: deceptively similar, NOT the same subject
    EvalCase(
        id="miss-01-gds-vs-seo",
        category="near_miss_non_match",
        existing_topic="gds_connectivity",
        existing_statement=(
            "GDS connectivity (Sabre/Amadeus) is a blocker for enterprise "
            "hotel prospects."
        ),
        transcript_text=(
            "Alex: Marketing asked whether we could integrate with Google "
            "Business Profile listings for local SEO - unrelated to any "
            "reservations or GDS work."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["google business", "seo"],
        notes="Shares the word 'integration'/'Google' territory but is a genuinely different subject (marketing/SEO vs. reservations distribution). match_topic() must return None here, not bridge to gds_connectivity.",
    ),
    EvalCase(
        id="miss-02-pricing-vs-currency-display",
        category="near_miss_non_match",
        existing_topic="dynamic_pricing_rules",
        existing_statement=(
            "Rule-based dynamic pricing adjusts nightly rates based on "
            "occupancy."
        ),
        transcript_text=(
            "Jordan: Finance asked about dynamic currency conversion at "
            "checkout for international guests - a payments display "
            "feature, not related to nightly rate pricing rules."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["currency conversion", "checkout"],
        notes="Both mention 'dynamic' and pricing/currency, but rate-setting logic and checkout currency display are different features entirely.",
    ),
    EvalCase(
        id="miss-03-housekeeping-vs-maintenance-app",
        category="near_miss_non_match",
        existing_topic="housekeeping_mobile_app",
        existing_statement=(
            "A mobile app for housekeeping staff to mark rooms clean or "
            "dirty."
        ),
        transcript_text=(
            "Priya: Product discussed a separate maintenance-request "
            "mobile app for engineering staff to log broken equipment - "
            "different team, different app, different users than "
            "housekeeping."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["maintenance", "engineering staff"],
        notes="Both are 'a mobile app for staff' but serve different departments and use cases - the transcript itself flags the distinction, testing whether the model respects that or pattern-matches on 'staff mobile app'.",
    ),
    EvalCase(
        id="miss-04-guest-vs-internal-messaging",
        category="near_miss_non_match",
        existing_topic="guest_messaging_automation",
        existing_statement=(
            "Automated pre-arrival and post-checkout guest messaging "
            "templates."
        ),
        transcript_text=(
            "Sam: Support proposed automated internal messaging alerts for "
            "staff shift handovers - an internal ops tool, not guest-facing "
            "messaging."
        ),
        expected_matched_topic=None,
        expected_relationship="new",
        expected_fact_keywords=["shift handover", "internal"],
        notes="Both are 'automated messaging' but one is guest-facing and one is internal ops - a real risk category since 'messaging automation' is a plausible topic-string collision.",
    ),
]

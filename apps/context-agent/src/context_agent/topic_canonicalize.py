from __future__ import annotations

import re

# T085 (see docs/decisions - eval harness + Supermemory comparison): a pure,
# deterministic, zero-LLM safety net that catches near-duplicate topic
# strings before match_topic()'s expensive pairwise LLM loop ever runs.
# Ported the IDEA, not the code, from supermemoryai/company-brain's
# `canonicalizeProposedTags`/`canonicalMatch` (open-sourced Sept 2026) -
# theirs is TypeScript over a different tag/kind data model; this is a
# from-scratch Python version scoped to our plain topic strings.
#
# What this is NOT: a replacement for match_topic(). It only catches
# formatting/spelling variants of the SAME wording ("GDS connectivity" vs
# "gds_connectivity" vs "GDS Connectivity") - real semantic drift ("Enterprise
# SSO" vs "SSO for Enterprise Customers", genuinely different wording for the
# same subject) still needs match_topic()'s real judgment. This function is
# only ever a pre-filter: if it finds nothing, _retrieve() falls through to
# match_topic() exactly as before.

# Common words that appear across many unrelated topics and shouldn't count
# as a signal of similarity on their own (mirrors company-brain's own
# GENERIC_TOKENS stoplist, trimmed to what's plausible in our domain).
_GENERIC_TOKENS = {
    "the",
    "and",
    "for",
    "with",
    "data",
    "team",
    "plan",
    "work",
    "app",
    "api",
    "update",
    "updates",
    "status",
    "issue",
    "issues",
    "note",
    "notes",
    "general",
    "new",
    "old",
}

_MIN_TOKEN_LEN = 3
_MIN_AKIN_PREFIX_LEN = 4
# A single shared word (even a non-generic one - "dynamic", "mobile") isn't
# enough evidence on its own: real eval cases (miss-02, miss-03) share
# exactly one substantial word between genuinely different subjects
# ("dynamic pricing rules" vs "dynamic currency conversion", "housekeeping
# mobile app" vs "maintenance mobile app"). Requiring at least two distinct
# matched tokens avoids exactly this false-positive shape; a full-string
# match (checked first, above) already covers simple one-word-topic
# renamings without needing this fallback at all.
_MIN_MATCHED_TOKENS = 2


def normalize_topic_key(topic: str) -> str:
    """Lowercase, collapse any run of non-alphanumeric characters to a
    single underscore, and trim - so "GDS connectivity", "gds_connectivity"
    and "GDS-Connectivity!" all normalize to the same key."""
    key = re.sub(r"[^a-z0-9]+", "_", topic.strip().lower())
    return key.strip("_")


def _tokens(key: str) -> set[str]:
    return {
        token
        for token in key.split("_")
        if len(token) >= _MIN_TOKEN_LEN and token not in _GENERIC_TOKENS
    }


def _tokens_akin(a: str, b: str) -> bool:
    """True if two tokens are the same, or one is a plausible prefix of the
    other (e.g. "connect"/"connectivity", catching simple pluralization or
    truncation - not a general fuzzy-match, deliberately conservative)."""
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= _MIN_AKIN_PREFIX_LEN and longer.startswith(shorter)


def canonicalize_topic(candidate_topic: str, existing_topics: list[str]) -> str | None:
    """Return the existing topic string `candidate_topic` should snap onto,
    or None if nothing is a close enough formatting/spelling variant.

    Checks an exact match on the normalized key first (case/punctuation/
    separator-insensitive), then falls back to a conservative token-overlap
    check (at least one shared, non-generic token of length >= 4). Never
    invents a new topic and never claims a match on genuinely different
    wording - that judgment call stays with match_topic().
    """
    candidate_key = normalize_topic_key(candidate_topic)
    if not candidate_key:
        return None

    for existing in existing_topics:
        if normalize_topic_key(existing) == candidate_key:
            return existing

    candidate_tokens = _tokens(candidate_key)
    if not candidate_tokens:
        return None

    for existing in existing_topics:
        existing_tokens = _tokens(normalize_topic_key(existing))
        matched = {a for a in candidate_tokens if any(_tokens_akin(a, b) for b in existing_tokens)}
        if len(matched) >= _MIN_MATCHED_TOKENS:
            return existing

    return None

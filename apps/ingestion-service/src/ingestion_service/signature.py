"""T049: verify a webhook really came from Anarlog.

Per docs/research/anarlog.md §4 (Anarlog's own docs, confirmed): HMAC-SHA256
over the RAW request body, keyed with the endpoint's `whsec_...` secret,
sent as `x-anarlog-signature: sha256=<hex>`.

Not yet handled here (flagged, not silently ignored):
  - Per-employee secrets. There's one shared `ANARLOG_WEBHOOK_SECRET` for
    the whole service - see docs/research/anarlog.md §7 and T046's status
    note. Fine for one person's dev testing; not fine for more than one
    RMS employee sending webhooks to the same endpoint.
  - Replay protection (`x-anarlog-timestamp` staleness) and delivery-id
    dedup on retries - Anarlog's docs recommend both; neither is done
    here or anywhere else yet (also flagged in T046's status note).
"""

from __future__ import annotations

import hashlib
import hmac

# Anarlog's docs don't hyphenate/prefix anything else onto the digest -
# just this literal prefix before the hex HMAC.
_SIGNATURE_PREFIX = "sha256="


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """True if `signature_header` is a valid HMAC-SHA256 of `body` under
    `secret`. False for a missing header, wrong secret, or tampered body -
    never raises, so callers can turn a False straight into a 401.
    """
    if not signature_header:
        return False

    expected = _SIGNATURE_PREFIX + hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    # Constant-time comparison - a naive `==` leaks timing information
    # about how many leading characters matched.
    return hmac.compare_digest(signature_header, expected)

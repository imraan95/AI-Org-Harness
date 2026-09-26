"""T044: ingestion-service scaffold. T046: persist real events to Supabase.
T047: enqueue a transcript.ingested job for context-agent to pick up.
T049: verify the webhook's signature before doing anything else with it.
"""

from __future__ import annotations

import json
import logging
import os

from db import (
    enqueue_job,
    get_session_factory,
    insert_transcript,
    insert_transcript_chunks,
)
from fastapi import FastAPI, HTTPException, Request

from .normalise import build_transcript_chunks, normalise_anarlog_payload
from .signature import verify_signature

logger = logging.getLogger(__name__)

# A real deployment MUST override this via env var, to the actual
# `whsec_...` secret copied from Anarlog's Settings -> Developers ->
# Webhooks page when the endpoint was registered - this placeholder only
# exists so local tests (which sign with the same fallback) work without
# extra setup. Same pattern as infra/openviking-config/ov.conf's root key.
ANARLOG_WEBHOOK_SECRET = os.environ.get(
    "ANARLOG_WEBHOOK_SECRET", "dev-secret-placeholder-changeme"
)

# Without this, our INFO-level logs are silently dropped when run for real
# (python defaults the root logger to WARNING) - uvicorn only configures its
# own "uvicorn.access"/"uvicorn.error" loggers, not ours. pytest's `caplog`
# fixture masks this in tests by forcing capture regardless of level, which
# is why T044's test passed even though this line was missing.
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ingestion-service")

# `webhook.test` (data = {"message": "..."}, see docs/research/anarlog.md
# §8) and any other future event type are acknowledged with 200 but not
# normalised or persisted - only these carry a real `data.meeting` payload.
#
# Of these two, only `note.enhanced` is actually persisted: it fires later
# than `meeting.completed`, for the SAME meeting, once Anarlog's own AI
# summary is ready. Persisting both would try to insert two rows sharing
# the same Transcript.id (the meeting id) - there's no dedup/upsert task
# yet (flagged in build-plan.md's T046 status), so for now we wait for the
# richer, later event and just log-and-ack `meeting.completed`.
_PERSISTABLE_EVENTS = {"note.enhanced"}


@app.post("/webhooks/anarlog")
async def receive_anarlog_webhook(request: Request) -> dict[str, str]:
    body = await request.body()

    if not verify_signature(
        ANARLOG_WEBHOOK_SECRET, body, request.headers.get("x-anarlog-signature")
    ):
        logger.warning("Rejected Anarlog webhook: invalid or missing signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    logger.info(
        "Received Anarlog webhook payload (%d bytes): %s",
        len(body),
        body.decode("utf-8", errors="replace"),
    )

    payload = json.loads(body)
    if payload.get("event") not in _PERSISTABLE_EVENTS:
        return {"status": "received"}

    transcript, chunk_texts = normalise_anarlog_payload(payload)

    # Created fresh per request rather than once at module scope: a
    # SQLAlchemy async engine binds to whichever event loop is running
    # when it's first used, and reusing one across requests that run on
    # different loops (as pytest-asyncio's function-scoped loops do in
    # tests) raises "Event loop is closed". A real per-request cost under
    # uvicorn's one long-lived loop, but simplest thing that's actually
    # correct - revisit if/when ingestion-service needs to handle real
    # request volume.
    session_factory = get_session_factory()

    chunks = await build_transcript_chunks(transcript.id, chunk_texts)

    async with session_factory() as session:
        await insert_transcript(session, transcript)
        await insert_transcript_chunks(session, transcript.id, chunks)
        await enqueue_job(
            session, "transcript.ingested", {"transcript_id": transcript.id}
        )

    return {"status": "received"}

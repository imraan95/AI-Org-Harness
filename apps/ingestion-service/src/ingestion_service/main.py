"""T044: ingestion-service scaffold.

Just a live HTTP endpoint that receives an Anarlog webhook and logs the raw
body. No parsing, verification, or persistence yet - that's T045 (payload
normalisation, once S2's research resolves Anarlog's real payload shape and
signature scheme) and T046 (persist to Supabase).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

app = FastAPI(title="ingestion-service")


@app.post("/webhooks/anarlog")
async def receive_anarlog_webhook(request: Request) -> dict[str, str]:
    body = await request.body()
    logger.info(
        "Received Anarlog webhook payload (%d bytes): %s",
        len(body),
        body.decode("utf-8", errors="replace"),
    )
    return {"status": "received"}

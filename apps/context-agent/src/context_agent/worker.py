"""T048: dequeues `transcript.ingested` jobs and runs them through the
pipeline.

A single callable step rather than a standing loop - simple enough to run
on demand (tests, this module's own future callers) or drive from an
actual polling loop later without changing this function.
"""

from __future__ import annotations

import logging

from db import dequeue_job, get_transcript, mark_job_done
from knowledge_model import KnowledgeRecord
from llm_router import LLM
from openviking_client import OpenVikingClient
from sqlalchemy.ext.asyncio import AsyncSession

from .pipeline import process_transcript

logger = logging.getLogger(__name__)


async def run_worker_once(
    session: AsyncSession, llm: LLM, openviking: OpenVikingClient
) -> list[KnowledgeRecord] | None:
    """Claim and process the oldest pending job, if there is one.

    Returns the knowledge records `process_transcript` wrote, `None` if
    the queue was empty, and `[]` if the job's transcript no longer
    exists (logged, job still marked done - nothing to retry).
    """
    job = await dequeue_job(session)
    if job is None:
        return None

    if job.type != "transcript.ingested":
        # Only job type this codebase creates today (T047) - defensive,
        # not expected to be hit yet. Mark it done rather than leaving it
        # stuck "claimed" forever with nothing to process it.
        logger.warning("Unknown job type %r (job %s) - skipping", job.type, job.id)
        await mark_job_done(session, job.id)
        return []

    transcript_id = job.payload.get("transcript_id")
    transcript = await get_transcript(session, transcript_id)
    if transcript is None:
        logger.warning(
            "Job %s references transcript %r, which no longer exists",
            job.id,
            transcript_id,
        )
        await mark_job_done(session, job.id)
        return []

    written = await process_transcript(transcript, llm, openviking)
    await mark_job_done(session, job.id)
    return written

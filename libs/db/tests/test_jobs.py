from sqlalchemy import select

from db import JobRow, dequeue_job, enqueue_job, get_engine, get_session_factory, mark_job_done


async def test_enqueue_dequeue_mark_done_lifecycle():
    engine = get_engine()
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        job_id = await enqueue_job(session, "test.job", {"foo": "bar"})

    async with session_factory() as session:
        claimed = await dequeue_job(session)

    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.status == "claimed"

    # A second dequeue must not return the same job again.
    async with session_factory() as session:
        second = await dequeue_job(session)
    assert second is None or second.id != job_id

    async with session_factory() as session:
        await mark_job_done(session, job_id)

    async with session_factory() as session:
        result = await session.execute(select(JobRow).where(JobRow.id == job_id))
        row = result.scalar_one()

    await engine.dispose()

    assert row.status == "done"

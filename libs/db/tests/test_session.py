from sqlalchemy import text

from db import get_engine, get_session_factory


async def test_session_select_1_and_closes_cleanly():
    engine = get_engine()
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    await engine.dispose()

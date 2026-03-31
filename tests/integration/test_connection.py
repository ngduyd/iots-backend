import pytest
from app.services.database import get_db_pool

@pytest.mark.asyncio
async def test_db_connection():
    pool = await get_db_pool()
    assert pool is not None
    async with pool.acquire() as conn:
        res = await conn.fetchval("SELECT 1")
        assert res == 1

import asyncio
import json
import asyncpg

from app.core import config

db_pool = None
_pool_lock = asyncio.Lock()

async def _init_connection(connection):
    await connection.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )
    await connection.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )

async def get_db_pool():
    global db_pool

    if db_pool is not None:
        return db_pool

    async with _pool_lock:
        if db_pool is not None:
            return db_pool

        try:
            db_pool = await asyncpg.create_pool(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                min_size=1,
                max_size=10,
                init=_init_connection,
            )
            return db_pool
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            return None

async def close_db():
    global db_pool
    if db_pool is not None:
        await db_pool.close()
        db_pool = None

async def execute(query, *args):
    pool = await get_db_pool()
    if pool is None:
        return None
    async with pool.acquire() as connection:
        return await connection.execute(query, *args)

async def fetch(query, *args):
    pool = await get_db_pool()
    if pool is None:
        return []
    async with pool.acquire() as connection:
        lock_timeout_ms = max(1, config.DB_READ_LOCK_TIMEOUT_MS)
        statement_timeout_ms = max(1, config.DB_READ_STATEMENT_TIMEOUT_MS)
        async with connection.transaction(readonly=True, isolation="read_committed"):
            await connection.execute(f"SET LOCAL lock_timeout = '{lock_timeout_ms}ms';")
            await connection.execute(f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms';")
            rows = await connection.fetch(query, *args)
            return [dict(row) for row in rows]

async def fetchrow(query, *args):
    pool = await get_db_pool()
    if pool is None:
        return None
    async with pool.acquire() as connection:
        normalized = query.lstrip().upper()
        if normalized.startswith("SELECT"):
            lock_timeout_ms = max(1, config.DB_READ_LOCK_TIMEOUT_MS)
            statement_timeout_ms = max(1, config.DB_READ_STATEMENT_TIMEOUT_MS)
            async with connection.transaction(readonly=True, isolation="read_committed"):
                await connection.execute(f"SET LOCAL lock_timeout = '{lock_timeout_ms}ms';")
                await connection.execute(f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms';")
                row = await connection.fetchrow(query, *args)
                return dict(row) if row else None
        row = await connection.fetchrow(query, *args)
        return dict(row) if row else None

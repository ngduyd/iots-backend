import asyncio
import asyncpg
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

os.environ["DB_NAME"] = "test_db"
from app.core import config
config.DB_NAME = "test_db"

from app.services import database

async def main():
    print(f"Connecting to postgres to recreate {config.DB_NAME}...")
    try:
        conn = await asyncpg.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database="postgres"
        )
        await conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'test_db' AND pid <> pg_backend_pid()")
        await conn.execute('DROP DATABASE IF EXISTS "test_db"')
        await conn.execute('CREATE DATABASE "test_db"')
        await conn.close()
        print("Database recreated.")
    except Exception as e:
        print(f"Error recreating DB: {e}")
        return

    print("Initializing tables...")
    await database.init_db()
    print("Ensuring default users...")
    await database.ensure_default_admin_user()
    
    # Verify
    pool = await database.get_db_pool()
    async with pool.acquire() as conn:
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        print(f"Final tables: {[t['table_name'] for t in tables]}")
        user_count = await conn.fetchval("SELECT count(*) FROM users")
        print(f"User count: {user_count}")
    await database.close_db()

if __name__ == "__main__":
    asyncio.run(main())

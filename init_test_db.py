import asyncio
import os

# Force test database configuration
os.environ["DB_NAME"] = "test_db"

from app.core import config
config.DB_NAME = "test_db"

from app.services import database

async def main():
    print(f"Initializing {config.DB_NAME}...")
    await database.init_db()
    await database.ensure_default_admin_user()
    print("Done.")
    
    # Verify tables
    pool = await database.get_db_pool()
    async with pool.acquire() as conn:
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        print("Tables created:")
        for t in tables:
            print(f"- {t['table_name']}")
    await database.close_db()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import asyncpg
from app.core import config

async def check_tables():
    print(f"Connecting to {config.DB_HOST}:{config.DB_PORT} db={config.DB_NAME}")
    try:
        conn = await asyncpg.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        print("Tables in DB:")
        for t in tables:
            print(f"- {t['table_name']}")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_tables())

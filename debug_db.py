import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "123456")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db_name = "test_db"
    
    print(f"Connecting to {db_name} at {host}:{port} as {user}...")
    try:
        conn = await asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=db_name
        )
        print("Connection successful!")
        val = await conn.fetchval("SELECT 1")
        print(f"Fetch value: {val}")
        await conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())

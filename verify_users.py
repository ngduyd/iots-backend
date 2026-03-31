import asyncio
import asyncpg
import os

async def main():
    conn = await asyncpg.connect(
        user='postgres',
        password='newpassword',
        host='localhost',
        database='test_db'
    )
    rows = await conn.fetch("SELECT user_id, username, role FROM users")
    print(f"Users in test_db: {rows}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

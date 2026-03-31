import asyncio
import asyncpg
import sys
import os

# DO NOT import app or database here to avoid creating pools in this process

async def main():
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", 5432))
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "123456")
    db_name = os.environ.get("DB_NAME", "test_db")
    
    print(f"Recreating database {db_name}...")
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres"
        )
        await conn.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}' AND pid <> pg_backend_pid()")
        await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await conn.execute(f'CREATE DATABASE "{db_name}"')
        await conn.close()
        print("Success.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

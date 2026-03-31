import asyncio
import sys
import os
import pytest
from dotenv import load_dotenv

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ["PYTHONPATH"] = project_root
os.environ["DB_NAME"] = "test_db"
load_dotenv()

from app.core import config
config.DB_NAME = "test_db"
from app.services import database

async def setup_test_db():
    print(f"Cleaning and initializing {config.DB_NAME}...")
    import asyncpg
    try:
        # Create test_db if it doesn't exist (connect to postgres first)
        conn = await asyncpg.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database="postgres"
        )
        await conn.execute(f'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = \'{config.DB_NAME}\' AND pid <> pg_backend_pid()')
        await conn.execute(f'DROP DATABASE IF EXISTS "{config.DB_NAME}"')
        await conn.execute(f'CREATE DATABASE "{config.DB_NAME}"')
        await conn.close()
        
        # Initialize tables
        await database.init_db()
        await database.ensure_default_admin_user()
        print("Test database ready.")
    except Exception as e:
        print(f"Failed to setup test database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print(f"Project root: {project_root}")
    
    # Setup database synchronously before pytest
    asyncio.run(setup_test_db())

    # Run pytest
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/integration"]
    sys.exit(pytest.main(args))

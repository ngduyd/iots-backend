import os
import sys
import asyncio
import pytest
import asyncpg
from httpx import ASGITransport, AsyncClient

import subprocess

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

os.environ["DB_NAME"] = "test_db"
from app.core import config
config.DB_NAME = "test_db"

from app.main import app
from app.services import database

@pytest.fixture(scope="session", autouse=True)
async def setup_db_structure():
    """Ensure the test database is clean and initialized for the whole session."""
    # 1. Recreate DB (using external script to avoid loop issues)
    print("Recreating test_db...")
    env = os.environ.copy()
    subprocess.run([sys.executable, "clean_db.py"], env=env, check=True)
    
    # 2. Reset the pool and initialize
    database.db_pool = None
    await database.init_db()
    await database.ensure_default_admin_user()
    print("Test database initialization complete.")
    
    yield
    
    await database.close_db()

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def api_client():
    """Client for integration tests. App lifespan is handled here."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def real_db():
    """Returns the app's database pool."""
    pool = await database.get_db_pool()
    return pool

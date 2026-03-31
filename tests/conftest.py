import os
import sys
import pytest
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import AsyncClient
from app.main import app
from app.services import database
from app.security import get_current_user_record, require_admin
from unittest.mock import MagicMock, AsyncMock

# Thiết lập biến môi trường để dùng cho test
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/test_db"
os.environ["SUPERADMIN_USERNAME"] = "testadmin"
os.environ["SUPERADMIN_PASSWORD"] = "testpassword"

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

class SimpleAsyncContextManager:
    """Một Async Context Manager đơn giản trả về đối tượng được truyền vào."""
    def __init__(self, value):
        self.value = value
    async def __aenter__(self):
        return self.value
    async def __aexit__(self, exc_type, exc, tb):
        pass

class FakeConnection:
    """Lớp giả lập Connection của asyncpg - KHÔNG sử dụng MagicMock để tránh nhầm lẫn coroutine."""
    def __init__(self):
        self.fetchrow = AsyncMock()
        self.fetch = AsyncMock()
        self.execute = AsyncMock()
        self.executemany = AsyncMock()
    
    def transaction(self, **kwargs):
        return SimpleAsyncContextManager(self)

class FakePool:
    """Lớp giả lập Pool của asyncpg."""
    def __init__(self, connection):
        self.connection = connection
        # acquire không phải là async function trong asyncpg, nó trả về một context manager
        self.acquire = MagicMock(side_effect=self._acquire)
    
    def _acquire(self, **kwargs):
        return SimpleAsyncContextManager(self.connection)

@pytest.fixture
async def mock_db(monkeypatch):
    """Giả lập database pool sử dụng các lớp Fake tường minh."""
    conn = FakeConnection()
    pool = FakePool(conn)
    
    # Patch get_db_pool: một async function trả về mock_pool
    async def mock_get_pool():
        return pool
        
    monkeypatch.setattr(database, "get_db_pool", mock_get_pool)
    
    return pool, conn

@pytest.fixture
async def authenticated_client(client, monkeypatch):
    """Giả lập một client đã đăng nhập bằng dependency_overrides."""
    mock_user = {"user_id": 1, "username": "testadmin", "role": "superadmin", "group_id": None}
    
    # Ghi đè các dependencies của FastAPI
    app.dependency_overrides[get_current_user_record] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    
    yield client
    
    # Xóa ghi đè sau khi test xong
    app.dependency_overrides.clear()

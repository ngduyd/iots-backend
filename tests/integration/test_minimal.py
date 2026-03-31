import pytest
import asyncio
import os
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services import database
from app.core import config

@pytest.mark.asyncio
async def test_minimal_login():
    # 1. Setup DB
    os.environ["DB_NAME"] = "test_db"
    config.DB_NAME = "test_db"
    await database.init_db()
    await database.ensure_default_admin_user()
    
    # 2. Test Login
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_data = {
            "username": config.SUPERADMIN_USERNAME,
            "password": config.SUPERADMIN_PASSWORD
        }
        response = await ac.post("/api/auth/login", json=login_data)
        print(f"DEBUG: Response status: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")
        assert response.status_code == 200
    
    await database.close_db()

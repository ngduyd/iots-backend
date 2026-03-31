import pytest
from unittest.mock import AsyncMock
from app.services import database

@pytest.mark.asyncio
async def test_create_user_success(monkeypatch):
    mock_user = {"user_id": 1, "username": "testuser", "role": "user", "group_id": None}
    
    async def mock_fetchrow(query, *args):
        return mock_user
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    user = await database.create_user("testuser", "password123")
    assert user == mock_user

@pytest.mark.asyncio
async def test_create_user_error(monkeypatch):
    async def mock_fetchrow(query, *args):
        raise Exception("DB Error")
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    user = await database.create_user("testuser", "password123")
    assert user is None

@pytest.mark.asyncio
async def test_get_user_success(monkeypatch):
    mock_user = {"user_id": 1, "username": "testuser"}
    
    async def mock_fetchrow(query, *args):
        return mock_user
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    user = await database.get_user(1)
    assert user == mock_user

@pytest.mark.asyncio
async def test_get_user_by_username_success(monkeypatch):
    mock_user = {"user_id": 1, "username": "testuser"}
    
    async def mock_fetchrow(query, *args):
        return mock_user
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    user = await database.get_user_by_username("testuser")
    assert user == mock_user

@pytest.mark.asyncio
async def test_update_user_without_password(monkeypatch):
    mock_user = {"user_id": 1, "username": "updated", "role": "admin"}
    
    async def mock_fetchrow(query, *args):
        return mock_user
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    user = await database.update_user(1, "updated", role="admin")
    assert user == mock_user

@pytest.mark.asyncio
async def test_update_user_with_password(monkeypatch):
    mock_user = {"user_id": 1, "username": "updated"}
    
    async def mock_fetchrow(query, *args):
        # Verify query contains password_hash if password is provided
        if "password_hash" in query:
            return mock_user
        return None
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    user = await database.update_user(1, "updated", password="newpassword")
    assert user == mock_user

@pytest.mark.asyncio
async def test_delete_user_success(monkeypatch):
    mock_row = {"user_id": 1}
    
    async def mock_fetchrow(query, *args):
        return mock_row
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    result = await database.delete_user(1)
    assert result is True

@pytest.mark.asyncio
async def test_delete_user_failure(monkeypatch):
    async def mock_fetchrow(query, *args):
        return None
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    result = await database.delete_user(1)
    assert result is False

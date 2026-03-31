import pytest
from unittest.mock import AsyncMock
from app.services import database
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_save_image_analysis_success(monkeypatch):
    mock_row = {"image_id": "img123", "people_count": 5}
    async def mock_fetchrow(query, *args):
        return mock_row
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.save_image_analysis("img123", "cam1", "/path", 5)
    assert res == mock_row

@pytest.mark.asyncio
async def test_get_image_analysis_success(monkeypatch):
    mock_row = {"image_id": "img123"}
    async def mock_fetchrow(query, *args):
        return mock_row
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.get_image_analysis("img123")
    assert res == mock_row

@pytest.mark.asyncio
async def test_create_user_session_success(monkeypatch):
    mock_session = {"session_id": "sess123", "user_id": 1}
    async def mock_fetchrow(query, *args):
        return mock_session
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.create_user_session("sess123", 1, datetime.now() + timedelta(hours=1))
    assert res == mock_session

@pytest.mark.asyncio
async def test_get_user_session_success(monkeypatch):
    mock_session = {"session_id": "sess123"}
    async def mock_fetchrow(query, *args):
        return mock_session
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.get_user_session("sess123")
    assert res == mock_session

@pytest.mark.asyncio
async def test_get_active_user_session_success(monkeypatch):
    mock_session = {"session_id": "sess123", "is_active": True}
    async def mock_fetchrow(query, *args):
        return mock_session
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.get_active_user_session("sess123")
    assert res == mock_session

@pytest.mark.asyncio
async def test_touch_user_session_success(monkeypatch):
    mock_session = {"session_id": "sess123", "last_seen_at": datetime.now()}
    async def mock_fetchrow(query, *args):
        return mock_session
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.touch_user_session("sess123")
    assert res == mock_session

@pytest.mark.asyncio
async def test_revoke_user_session_success(monkeypatch):
    mock_row = {"session_id": "sess123"}
    async def mock_fetchrow(query, *args):
        return mock_row
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.revoke_user_session("sess123")
    assert res is True

@pytest.mark.asyncio
async def test_get_image_analysis_by_camera_last_10_minutes_success(monkeypatch):
    mock_rows = [{"image_id": "img123"}]
    async def mock_fetch(query, *args):
        return mock_rows
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    res = await database.get_image_analysis_by_camera_last_10_minutes("cam1")
    assert res == mock_rows

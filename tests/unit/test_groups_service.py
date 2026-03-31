import pytest
from unittest.mock import AsyncMock
from app.services import database

@pytest.mark.asyncio
async def test_create_group_success(monkeypatch):
    mock_group = {"group_id": 1, "name": "Test Group"}
    
    async def mock_fetchrow(query, *args):
        return mock_group
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    group = await database.create_group("Test Group")
    assert group == mock_group

@pytest.mark.asyncio
async def test_get_groups_success(monkeypatch):
    mock_groups = [{"group_id": 1, "name": "G1"}, {"group_id": 2, "name": "G2"}]
    
    async def mock_fetch(query, *args):
        return mock_groups
        
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    groups = await database.get_groups()
    assert groups == mock_groups

@pytest.mark.asyncio
async def test_get_group_success(monkeypatch):
    mock_group = {"group_id": 1, "name": "G1"}
    
    async def mock_fetchrow(query, *args):
        return mock_group
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    group = await database.get_group(1)
    assert group == mock_group

@pytest.mark.asyncio
async def test_update_group_success(monkeypatch):
    mock_group = {"group_id": 1, "name": "Updated G1"}
    
    async def mock_fetchrow(query, *args):
        return mock_group
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    group = await database.update_group(1, "Updated G1")
    assert group == mock_group

@pytest.mark.asyncio
async def test_delete_group_success(monkeypatch):
    mock_row = {"group_id": 1}
    
    async def mock_fetchrow(query, *args):
        return mock_row
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    result = await database.delete_group(1)
    assert result is True

@pytest.mark.asyncio
async def test_delete_group_failure(monkeypatch):
    async def mock_fetchrow(query, *args):
        return None
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    result = await database.delete_group(1)
    assert result is False

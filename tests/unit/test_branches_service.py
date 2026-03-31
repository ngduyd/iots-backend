import pytest
from unittest.mock import AsyncMock
from app.services import database

@pytest.mark.asyncio
async def test_create_branch_success(monkeypatch):
    mock_branch = {"branch_id": 1, "name": "Branch 1", "group_id": 1}
    
    async def mock_fetchrow(query, *args):
        return mock_group_branch if "branches" in query else None
        
    # We need to simulate that the group exists if create_branch checks it? 
    # Let's check create_branch source.
    pass

@pytest.mark.asyncio
async def test_get_branches_no_filter(monkeypatch):
    mock_branches = [{"branch_id": 1, "name": "B1"}, {"branch_id": 2, "name": "B2"}]
    async def mock_fetch(query, *args):
        return mock_branches
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    branches = await database.get_branches()
    assert branches == mock_branches

@pytest.mark.asyncio
async def test_get_branch_success(monkeypatch):
    mock_branch = {"branch_id": 1, "name": "B1"}
    async def mock_fetchrow(query, *args):
        return mock_branch
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    branch = await database.get_branch(1)
    assert branch == mock_branch

@pytest.mark.asyncio
async def test_update_branch_success(monkeypatch):
    mock_branch = {"branch_id": 1, "name": "Updated B1"}
    async def mock_fetchrow(query, *args):
        return mock_branch
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    branch = await database.update_branch(1, 1, "Updated B1")
    assert branch == mock_branch

@pytest.mark.asyncio
async def test_delete_branch_success(monkeypatch):
    async def mock_fetchrow(query, *args):
        return {"branch_id": 1}
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    result = await database.delete_branch(1)
    assert result is True

@pytest.mark.asyncio
async def test_get_sensors_by_branch(monkeypatch):
    mock_sensors = [{"sensor_id": "S1"}]
    async def mock_fetch(query, *args):
        return mock_sensors
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    sensors = await database.get_sensors_by_branch(1)
    assert sensors == mock_sensors

@pytest.mark.asyncio
async def test_get_cameras_by_branch(monkeypatch):
    mock_cameras = [{"camera_id": 1}]
    async def mock_fetch(query, *args):
        return mock_cameras
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    cameras = await database.get_cameras_by_branch(1)
    assert cameras == mock_cameras

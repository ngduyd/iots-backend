import pytest
from unittest.mock import AsyncMock
from app.services import database

@pytest.mark.asyncio
async def test_add_camera_success(monkeypatch):
    mock_camera = {"camera_id": "CAM123", "name": "Cam 1", "activate": False}
    
    async def mock_fetchrow(query, *args):
        return mock_camera
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    camera = await database.add_camera("Cam 1", branch_id=1)
    assert camera == mock_camera

@pytest.mark.asyncio
async def test_get_cameras_by_branch_success(monkeypatch):
    mock_cameras = [{"camera_id": "CAM1", "branch_id": 1}]
    
    async def mock_fetch(query, *args):
        return mock_cameras
        
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    cameras = await database.get_cameras_by_branch(1)
    assert cameras == mock_cameras

@pytest.mark.asyncio
async def test_get_camera_by_branch_success(monkeypatch):
    mock_camera = {"camera_id": "CAM1"}
    
    async def mock_fetchrow(query, *args):
        return mock_camera
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    camera = await database.get_camera_by_branch(1)
    assert camera == mock_camera

@pytest.mark.asyncio
async def test_update_camera_success(monkeypatch):
    mock_camera = {"camera_id": "CAM1", "name": "Updated Cam"}
    
    async def mock_fetchrow(query, *args):
        return mock_camera
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    camera = await database.update_camera("CAM1", name="Updated Cam")
    assert camera == mock_camera

@pytest.mark.asyncio
async def test_reset_camera_secret_success(monkeypatch):
    mock_camera = {"camera_id": "CAM1", "secret": "newsecret"}
    
    async def mock_fetchrow(query, *args):
        return mock_camera
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    camera = await database.reset_camera_secret("CAM1")
    assert camera["secret"] == "newsecret"

@pytest.mark.asyncio
async def test_delete_camera_success(monkeypatch):
    async def mock_fetchrow(query, *args):
        return {"camera_id": "CAM1"}
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    result = await database.delete_camera("CAM1")
    assert result is True

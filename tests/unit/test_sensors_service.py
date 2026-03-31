import pytest
from unittest.mock import AsyncMock
from app.services import database

@pytest.mark.asyncio
async def test_add_sensor_success(monkeypatch):
    mock_sensor = {"sensor_id": "SN123", "name": "Sensor 1", "status": "online"}
    
    async def mock_fetchrow(query, *args):
        return mock_sensor
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    sensor = await database.add_sensor("Sensor 1", branch_id=1)
    assert sensor == mock_sensor

@pytest.mark.asyncio
async def test_add_sensor_no_branch_id():
    sensor = await database.add_sensor("Sensor 1")
    assert sensor is None

@pytest.mark.asyncio
async def test_get_sensors_by_branch_success(monkeypatch):
    mock_sensors = [{"sensor_id": "SN123", "name": "Sensor 1"}]
    
    async def mock_fetch(query, *args):
        return mock_sensors
        
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    sensors = await database.get_sensors_by_branch(1)
    assert sensors == mock_sensors

@pytest.mark.asyncio
async def test_update_sensor_name_branch(monkeypatch):
    mock_sensor = {"sensor_id": "SN123", "name": "Updated Sensor"}
    
    async def mock_fetchrow(query, *args):
        return mock_sensor
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    sensor = await database.update_sensor("SN123", sensor_name="Updated Sensor", branch_id=2)
    assert sensor == mock_sensor

@pytest.mark.asyncio
async def test_update_sensor_delete(monkeypatch):
    mock_sensor = {"sensor_id": "SN123", "status": "deleted"}
    
    async def mock_fetchrow(query, *args):
        if "SET deleted_at = NOW()" in query:
             return mock_sensor
        return None
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    sensor = await database.update_sensor("SN123", delete=True)
    assert sensor == mock_sensor

@pytest.mark.asyncio
async def test_get_sensor_to_branch_mapping_success(monkeypatch):
    mock_rows = [{"sensor_id": "SN1", "branch_id": 1}, {"sensor_id": "SN2", "branch_id": 1}]
    
    async def mock_fetch(query, *args):
        return mock_rows
        
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    mapping = await database.get_sensor_to_branch_mapping()
    assert mapping == {"SN1": 1, "SN2": 1}

import pytest
from unittest.mock import AsyncMock
from app.services import database
import json

@pytest.mark.asyncio
async def test_create_alert_success(monkeypatch):
    mock_alert = {"alert_id": 1, "message": "High temp", "level": "warning"}
    
    async def mock_fetchrow(query, *args):
        return mock_alert
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    alert = await database.create_alert(1, "High temp", "warning")
    assert alert == mock_alert

@pytest.mark.asyncio
async def test_get_alerts_by_branch_success(monkeypatch):
    mock_alerts = [{"alert_id": 1, "message": "A1"}, {"alert_id": 2, "message": "A2"}]
    
    async def mock_fetch(query, *args):
        return mock_alerts
        
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    alerts = await database.get_alerts_by_branch(1)
    assert alerts == mock_alerts

@pytest.mark.asyncio
async def test_get_all_branch_thresholds_success(monkeypatch):
    mock_rows = [{"branch_id": 1, "thresholds": {"temp": 30}}]
    
    async def mock_fetch(query, *args):
        return mock_rows
        
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    thresholds = await database.get_all_branch_thresholds()
    assert thresholds == {1: {"temp": 30}}

@pytest.mark.asyncio
async def test_update_branch_thresholds_success(monkeypatch):
    async def mock_execute(query, *args):
        return "UPDATE 1"
        
    monkeypatch.setattr(database, "_execute", mock_execute)
    
    result = await database.update_branch_thresholds(1, {"temp": 35})
    assert result is True

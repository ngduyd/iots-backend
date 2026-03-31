import pytest
import requests
from datetime import datetime
from app.services import job_service, database

@pytest.mark.asyncio
async def test_get_job_data_single_batch_empty(monkeypatch):
    async def mock_get_branch_data_for_export(*args):
        return [], []
    monkeypatch.setattr(job_service, "get_branch_data_for_export", mock_get_branch_data_for_export)
    
    res = await job_service.get_job_data_single_batch(1, datetime.now(), datetime.now())
    assert res == []

@pytest.mark.asyncio
async def test_get_job_data_single_batch_with_data(monkeypatch):
    now = datetime.now()
    sensor_values = [
        {"value": {"co2": 500, "temp": 25}, "created_at": now},
        {"value": {"rh": 50}, "created_at": now + (datetime.fromtimestamp(1) - datetime.fromtimestamp(0))} # +1s
    ]
    people_counts = [
        {"people_count": 5, "created_at": now + (datetime.fromtimestamp(2) - datetime.fromtimestamp(0))} # +2s
    ]
    
    async def mock_get_branch_data_for_export(*args):
        return sensor_values, people_counts
    monkeypatch.setattr(job_service, "get_branch_data_for_export", mock_get_branch_data_for_export)
    
    res = await job_service.get_job_data_single_batch(1, now, now)
    assert len(res) > 0
    assert res[0]["co2"] == 500
    assert res[0]["people"] == 5

@pytest.mark.asyncio
async def test_process_and_notify_ai_server_no_data(monkeypatch):
    async def mock_get_batch(*args):
        return []
    monkeypatch.setattr(job_service, "get_job_data_single_batch", mock_get_batch)
    
    async def mock_update_status(job_id, status, **kwargs):
        assert status == "failed"
        return True
    monkeypatch.setattr(job_service, "update_job_status_db", mock_update_status)
    
    await job_service.process_and_notify_ai_server("j1", "secret", 1, datetime.now(), datetime.now(), {})

def test_get_job_defaults_data():
    defaults = job_service.get_job_defaults_data()
    assert "dataset" in defaults
    assert "features" in defaults["dataset"]

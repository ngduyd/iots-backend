import pytest
from unittest.mock import AsyncMock
from app.services import database
import json
import uuid
from datetime import datetime

@pytest.mark.asyncio
async def test_create_job_db_success(monkeypatch):
    mock_job = {"job_id": "job123", "status": "pending"}
    
    async def mock_fetchrow(query, *args):
        return mock_job
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    job = await database.create_job_db(
        "job123", 1, 1, "secret", {}, {}, {}, {}
    )
    assert job == mock_job

@pytest.mark.asyncio
async def test_get_job_db_success(monkeypatch):
    mock_job = {"job_id": "job123", "status": "pending"}
    
    async def mock_fetchrow(query, *args):
        return mock_job
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    job = await database.get_job_db("job123")
    assert job == mock_job

@pytest.mark.asyncio
async def test_get_image_analysis_by_camera_last_10_minutes_success(monkeypatch):
    mock_rows = [{"image_id": "img123"}]
    async def mock_fetch(query, *args):
        return mock_rows
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    res = await database.get_image_analysis_by_camera_last_10_minutes("cam1")
    assert res == mock_rows

@pytest.mark.asyncio
async def test_revoke_all_user_sessions_success(monkeypatch):
    async def mock_execute(query, *args):
        return "UPDATE 5"
    monkeypatch.setattr(database, "_execute", mock_execute)
    
    res = await database.revoke_all_user_sessions(1)
    assert res is True

@pytest.mark.asyncio
async def test_get_user_sessions_success(monkeypatch):
    mock_rows = [{"session_id": "s1"}]
    async def mock_fetch(query, *args):
        return mock_rows
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    res = await database.get_user_sessions(1)
    assert res == mock_rows

@pytest.mark.asyncio
async def test_delete_expired_user_sessions_success(monkeypatch):
    async def mock_execute(query, *args):
        return "DELETE 10"
    monkeypatch.setattr(database, "_execute", mock_execute)
    
    res = await database.delete_expired_user_sessions()
    assert res is True

@pytest.mark.asyncio
async def test_get_jobs_db_no_filter(monkeypatch):
    mock_jobs = [{"job_id": "job1"}, {"job_id": "job2"}]
    async def mock_fetch(query, *args):
        return mock_jobs
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    jobs = await database.get_jobs_db()
    assert jobs == mock_jobs

@pytest.mark.asyncio
async def test_update_job_status_db_success(monkeypatch):
    mock_job = {"job_id": "job123", "status": "completed"}
    
    async def mock_fetchrow(query, *args):
        return mock_job
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    job = await database.update_job_status_db("job123", "completed")
    assert job == mock_job

@pytest.mark.asyncio
async def test_cancel_job_db_success(monkeypatch):
    mock_job = {"job_id": "job123", "status": "cancelled"}
    
    async def mock_fetchrow(query, *args):
        return mock_job
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.cancel_job_db("job123")
    assert res == mock_job

@pytest.mark.asyncio
async def test_get_or_create_model_success(monkeypatch):
    import uuid
    mid = str(uuid.uuid4())
    mock_row = {"model_id": mid, "name": "M1"}
    async def mock_fetchrow(query, *args):
        return mock_row
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.get_or_create_model(1, mid, "M1")
    assert res == mock_row

@pytest.mark.asyncio
async def test_get_models_db_success(monkeypatch):
    mock_rows = [{"model_id": "m1"}]
    async def mock_fetch(query, *args):
        return mock_rows
    monkeypatch.setattr(database, "_fetch", mock_fetch)
    
    res = await database.get_models_db(1)
    assert res == mock_rows

@pytest.mark.asyncio
async def test_update_model_name_db_success(monkeypatch):
    import uuid
    mid = str(uuid.uuid4())
    mock_row = {"model_id": mid, "name": "New Name"}
    async def mock_fetchrow(query, *args):
        return mock_row
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.update_model_name_db(mid, "New Name", 1)
    assert res == mock_row

@pytest.mark.asyncio
async def test_delete_model_db_success(monkeypatch):
    import uuid
    mid = str(uuid.uuid4())
    mock_row = {"model_id": mid, "deleted_at": "now"}
    async def mock_fetchrow(query, *args):
        return mock_row
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    res = await database.delete_model_db(mid, 1)
    assert res == mock_row

@pytest.mark.asyncio
async def test_verify_job_data_exists_success(monkeypatch):
    # Mocking _fetchrow for each feature check
    async def mock_fetchrow(query, *args):
        return {"count": 10}
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    success, msg = await database.verify_job_data_exists(
        1, ["temp", "people"], datetime.now(), datetime.now()
    )
    assert success is True
    assert msg == ""

@pytest.mark.asyncio
async def test_verify_job_data_exists_missing_sensor(monkeypatch):
    # Mocking _fetchrow: returns 0 for sensors, 10 for people
    async def mock_fetchrow(query, *args):
        if "sensors" in query:
             return {"count": 0}
        return {"count": 10}
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    success, msg = await database.verify_job_data_exists(
        1, ["temp", "people"], datetime.now(), datetime.now()
    )
    assert success is False
    assert "temp" in msg

@pytest.mark.asyncio
async def test_verify_job_data_exists_missing_people(monkeypatch):
    # Mocking _fetchrow: returns 10 for sensors, 0 for image_analysis
    async def mock_fetchrow(query, *args):
        if "image_analysis" in query:
             return {"count": 0}
        return {"count": 10}
        
    monkeypatch.setattr(database, "_fetchrow", mock_fetchrow)
    
    success, msg = await database.verify_job_data_exists(
        1, ["temp", "people"], datetime.now(), datetime.now()
    )
    assert success is False
    assert "people" in msg

import pytest
from app.core import config
from uuid import uuid4

@pytest.mark.asyncio
async def test_sensors_cameras_flow(api_client):
    # 1. Login
    login_data = {"username": config.SUPERADMIN_USERNAME, "password": config.SUPERADMIN_PASSWORD}
    await api_client.post("/api/auth/login", json=login_data)
    
    # 2. Create Group & Branch
    group_res = await api_client.post("/api/groups", json={"name": f"G-{uuid4().hex[:4]}"})
    group_id = group_res.json()["data"]["group_id"]
    branch_res = await api_client.post("/api/branches", json={"name": f"B-{uuid4().hex[:4]}", "group_id": group_id})
    branch_id = branch_res.json()["data"]["branch_id"]
    
    # 3. Create Sensor
    sensor_name = f"Sensor-{uuid4().hex[:4]}"
    sensor_res = await api_client.post("/api/sensors", json={"name": sensor_name, "branch_id": branch_id})
    assert sensor_res.status_code == 200
    sensor_id = sensor_res.json()["data"]["sensor_id"]
    
    # 4. Create Camera
    camera_name = f"Camera-{uuid4().hex[:4]}"
    camera_res = await api_client.post("/api/cameras", json={"name": camera_name, "branch_id": branch_id, "activate": True})
    assert camera_res.status_code == 200
    camera_id = camera_res.json()["data"]["camera_id"]
    
    # 5. List Sensors & Cameras for branch
    sensors_res = await api_client.get("/api/sensors")
    assert any(s["sensor_id"] == sensor_id for s in sensors_res.json()["data"]["items"])
    
    cameras_res = await api_client.get("/api/cameras")
    assert any(c["camera_id"] == camera_id for c in cameras_res.json()["data"]["items"])
    
    # 6. Verify and Cleanup (optional)

import pytest
from app.core import config
from uuid import uuid4
import asyncio

@pytest.mark.asyncio
async def test_alert_generation_flow(api_client, real_db):
    # 1. Login
    login_data = {"username": config.SUPERADMIN_USERNAME, "password": config.SUPERADMIN_PASSWORD}
    await api_client.post("/api/auth/login", json=login_data)
    
    # 2. Create Group & Branch with low thresholds
    group_res = await api_client.post("/api/groups", json={"name": f"AlertGroup-{uuid4().hex[:4]}"})
    group_id = group_res.json()["data"]["group_id"]
    
    branch_data = {
        "name": f"AlertBranch-{uuid4().hex[:4]}",
        "group_id": group_id,
        "thresholds": {
            "temp_max": 30.0,  # Low threshold to trigger alert
            "co2_max": 500
        }
    }
    branch_res = await api_client.post("/api/branches", json=branch_data)
    branch_id = branch_res.json()["data"]["branch_id"]
    
    # 3. Create Sensor
    sensor_res = await api_client.post("/api/sensors", json={"name": "TempSensor", "branch_id": branch_id})
    sensor_id = sensor_res.json()["data"]["sensor_id"]
    
    # 4. Trigger alert via logic (using the internal service or simulating MQTT if possible)
    # Since we are doing integration test at API/Service level, we can use the database worker logic 
    # or just check if the API reports it.
    # Actually, let's simulate a sensor value insertion that should trigger alert logic.
    
    from app.services.database import add_sensor_value
    # Insert a value that exceeds 30.0
    await add_sensor_value(sensor_id, 35.0)
    
    # Wait a bit for async processing if any (though add_sensor_value usually triggers it sync in this context)
    await asyncio.sleep(1)
    
    # 5. Check alerts via API
    # Assuming there's a notification/alerts endpoint
    response = await api_client.get("/api/notifications")
    assert response.status_code == 200
    alerts = response.json()["data"]["items"]
    
    # Check if there's an alert for this branch/sensor
    # Note: NotificationManager might be involved.
    assert any(a["branch_id"] == branch_id for a in alerts)

import pytest

@pytest.mark.asyncio
async def test_list_sensors(authenticated_client, mock_db):
    """Test lấy danh sách sensors."""
    pool, conn = mock_db
    conn.fetch.return_value = [
        {"sensor_id": "S1", "name": "Sensor 1", "status": "online", "updated_at": None},
        {"sensor_id": "S2", "name": "Sensor 2", "status": "offline", "updated_at": None}
    ]
    
    response = await authenticated_client.get("/api/sensors")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert len(data["data"]["items"]) == 2
    assert data["data"]["items"][0]["sensor_id"] == "S1"

@pytest.mark.asyncio
async def test_add_sensor_api(authenticated_client, mock_db):
    """Test thêm mới sensor qua API."""
    pool, conn = mock_db
    conn.fetchrow.return_value = {
        "sensor_id": "NEW-S", "name": "New Sensor", "status": "offline", "updated_at": None
    }
    
    payload = {"name": "New Sensor", "branch_id": 1}
    response = await authenticated_client.post("/api/sensors", json=payload)
    
    assert response.status_code == 200
    assert response.json()["data"]["sensor_id"] == "NEW-S"
    # Kiểm tra gọi DB
    assert conn.fetchrow.called

@pytest.mark.asyncio
async def test_delete_sensor_api(authenticated_client, mock_db):
    """Test xóa sensor."""
    pool, conn = mock_db
    conn.fetchrow.return_value = {"sensor_id": "S1", "name": "Deleted", "status": "offline", "updated_at": None}
    
    response = await authenticated_client.delete("/api/sensors/S1")
    assert response.status_code == 200
    assert response.json()["message"] == "Sensor deleted successfully"

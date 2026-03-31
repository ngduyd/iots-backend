import pytest

@pytest.mark.asyncio
async def test_list_branches(authenticated_client, mock_db):
    """Test lấy danh sách các chi nhánh."""
    pool, conn = mock_db
    conn.fetch.return_value = [
        {"branch_id": 1, "name": "Branch HCM", "address": "Dist 1", "group_id": 1},
        {"branch_id": 2, "name": "Branch HN", "address": "Cau Giay", "group_id": 1}
    ]
    
    response = await authenticated_client.get("/api/branches")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["data"][0]["name"] == "Branch HCM"

@pytest.mark.asyncio
async def test_create_branch(authenticated_client, mock_db):
    """Test tạo chi nhánh mới."""
    pool, conn = mock_db
    conn.fetchrow.return_value = {"branch_id": 3, "name": "New Branch", "address": "Da Nang", "group_id": 1}
    
    payload = {"name": "New Branch", "address": "Da Nang", "group_id": 1}
    response = await authenticated_client.post("/api/branches", json=payload)
    
    assert response.status_code == 200
    assert response.json()["data"]["branch_id"] == 3

@pytest.mark.asyncio
async def test_get_branch_sensors(authenticated_client, mock_db):
    """Test lấy thông số sensors của chi nhánh."""
    pool, conn = mock_db
    # Mock kết quả fetchrow (kiểm tra branch tồn tại)
    conn.fetchrow.return_value = {"branch_id": 1, "name": "Branch HCM", "group_id": 1}
    # Mock kết quả fetch (lấy danh sách sensors)
    conn.fetch.return_value = [
        {"sensor_id": "SN1", "name": "Temp 1", "value": "25.5", "type": "temperature", "status": "online", "updated_at": "2024-01-01T00:00:00"}
    ]
    
    response = await authenticated_client.get("/api/branches/1/sensors")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]["items"]) == 1

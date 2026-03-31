import pytest

@pytest.mark.asyncio
async def test_list_cameras(authenticated_client, mock_db):
    """Test lấy danh sách camera."""
    pool, conn = mock_db
    conn.fetch.return_value = [
        {"camera_id": "C1", "name": "Entrance Cam", "rtsp_url": "rtsp://...", "status": "active", "activate": True, "branch_id": 1, "created_at": "2024-01-01T00:00:00", "secret": "s1"},
        {"camera_id": "C2", "name": "Parking Cam", "rtsp_url": "rtsp://...", "status": "inactive", "activate": False, "branch_id": 1, "created_at": "2024-01-01T00:00:00", "secret": "s2"}
    ]
    
    response = await authenticated_client.get("/api/cameras")
    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) == 2

@pytest.mark.asyncio
async def test_verify_stream_api(authenticated_client, mock_db):
    """Test API xác thực luồng RTSP."""
    pool, conn = mock_db
    conn.fetchrow.return_value = {"camera_id": "C1", "secret": "valid"}
    
    payload = {"name": "C1", "secret": "valid"}
    response = await authenticated_client.post("/api/cameras/verify-stream", data=payload)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Stream credentials verified"

@pytest.mark.asyncio
async def test_get_camera_by_id(authenticated_client, mock_db):
    """Test lấy thông tin chi tiết một camera."""
    pool, conn = mock_db
    conn.fetchrow.get.return_value = "C1" # Support .get() if it's a MagicMock
    conn.fetchrow.return_value = {
        "camera_id": "C1", "name": "Entrance Cam", "status": "active", "group_id": 1, "activate": True, "branch_id": 1, "created_at": "2024-01-01T00:00:00", "secret": "s1"
    }
    
    response = await authenticated_client.get("/api/cameras/C1")
    assert response.status_code == 200
    assert response.json()["data"]["camera_id"] == "C1"

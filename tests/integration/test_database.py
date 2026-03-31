import pytest
from app.services import database

@pytest.mark.asyncio
async def test_get_sensor_mocked(mock_db):
    """Test lấy thông tin sensor với database được mock."""
    pool, conn = mock_db
    # Setup mock return value cho AsyncMock fetchrow
    mock_row = {"sensor_id": "SN001", "name": "Test Sensor", "status": "online"}
    conn.fetchrow.return_value = mock_row

    sensor = await database.get_sensor("SN001")
    
    assert sensor is not None
    assert sensor["sensor_id"] == "SN001"
    # Kiểm tra xem hàm fetchrow có được gọi đúng câu lệnh SQL không
    args = conn.fetchrow.call_args[0]
    assert "SELECT sensor_id, name, branch_id, status, updated_at" in args[0]
    assert "WHERE sensor_id = $1" in args[0]

@pytest.mark.asyncio
async def test_add_sensor_mocked(mock_db):
    """Test thêm mới sensor."""
    pool, conn = mock_db
    mock_row = {"sensor_id": "NEW-ID", "name": "New Sensor", "status": "offline"}
    conn.fetchrow.return_value = mock_row

    result = await database.add_sensor(sensor_name="New Sensor", branch_id=1)
    
    assert result is not None
    assert result["sensor_id"] == "NEW-ID"
    # Kiểm tra lời gọi INSERT
    args = conn.fetchrow.call_args[0]
    assert "INSERT INTO sensors" in args[0]

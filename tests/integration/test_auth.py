import pytest
from app.core import config

@pytest.mark.asyncio
async def test_auth_flow(api_client):
    # 1. Login as superadmin
    login_data = {
        "username": config.SUPERADMIN_USERNAME,
        "password": config.SUPERADMIN_PASSWORD
    }
    response = await api_client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert "sid" in api_client.cookies
    
    # 2. Validate session
    response = await api_client.get("/api/auth/validate")
    assert response.status_code == 200
    assert response.json()["data"]["user"] == config.SUPERADMIN_USERNAME
    
    # 3. Get current user profile
    response = await api_client.get("/api/user")
    assert response.status_code == 200
    assert response.json()["data"]["username"] == config.SUPERADMIN_USERNAME
    
    # 4. Logout
    response = await api_client.post("/api/auth/logout")
    assert response.status_code == 200
    assert "sid" not in api_client.cookies or api_client.cookies.get("sid") == ""
    
    # 5. Verify session is invalid
    response = await api_client.get("/api/auth/validate")
    assert response.status_code == 401

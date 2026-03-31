import pytest
from app.core import config
from uuid import uuid4

@pytest.mark.asyncio
async def test_user_crud_flow(api_client):
    # 1. Login as superadmin
    login_data = {
        "username": config.SUPERADMIN_USERNAME,
        "password": config.SUPERADMIN_PASSWORD
    }
    await api_client.post("/api/auth/login", json=login_data)
    
    # 2. Create a group first (needed for user creation)
    group_name = f"test-group-{uuid4().hex[:6]}"
    group_res = await api_client.post("/api/groups", json={"name": group_name, "description": "Test Group"})
    assert group_res.status_code == 200
    group_id = group_res.json()["data"]["group_id"]
    
    # 3. Create a new user
    username = f"user-{uuid4().hex[:6]}"
    user_data = {
        "username": username,
        "password": "password123",
        "group_id": group_id,
        "role": "admin"
    }
    response = await api_client.post("/api/users", json=user_data)
    assert response.status_code == 200
    user_id = response.json()["data"]["user_id"]
    
    # 4. List users and check if new user is there
    response = await api_client.get("/api/users")
    assert response.status_code == 200
    users = response.json()["data"]
    assert any(u["username"] == username for u in users)
    
    # 5. Update user
    update_data = {"role": "user"}
    response = await api_client.put(f"/api/users/{user_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "user"
    
    # 6. Delete user
    response = await api_client.delete(f"/api/users/{user_id}")
    assert response.status_code == 200
    
    # 7. Verify deletion
    response = await api_client.get(f"/api/users/{user_id}")
    assert response.status_code == 404

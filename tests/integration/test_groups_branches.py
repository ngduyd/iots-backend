import pytest
from app.core import config
from uuid import uuid4

@pytest.mark.asyncio
async def test_group_branch_flow(api_client):
    # 1. Login
    login_data = {"username": config.SUPERADMIN_USERNAME, "password": config.SUPERADMIN_PASSWORD}
    await api_client.post("/api/auth/login", json=login_data)
    
    # 2. Create Group
    group_name = f"Group-{uuid4().hex[:6]}"
    group_res = await api_client.post("/api/groups", json={"name": group_name, "description": "Branch Test Group"})
    assert group_res.status_code == 200
    group_id = group_res.json()["data"]["group_id"]
    
    # 3. Create Branch in Group
    branch_name = f"Branch-{uuid4().hex[:6]}"
    branch_data = {
        "name": branch_name,
        "group_id": group_id,
        "location": "Hanoi",
        "thresholds": {
            "temp_max": 35.0,
            "co2_max": 1000
        }
    }
    branch_res = await api_client.post("/api/branches", json=branch_data)
    assert branch_res.status_code == 200
    branch_id = branch_res.json()["data"]["branch_id"]
    
    # 4. Verify Branch details and thresholds
    get_res = await api_client.get(f"/api/branches/{branch_id}")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["name"] == branch_name
    assert get_res.json()["data"]["thresholds"]["temp_max"] == 35.0
    
    # 5. Update Branch
    update_res = await api_client.put(f"/api/branches/{branch_id}", json={"location": "Saigon"})
    assert update_res.status_code == 200
    assert update_res.json()["data"]["location"] == "Saigon"
    
    # 6. Delete Branch
    del_branch = await api_client.delete(f"/api/branches/{branch_id}")
    assert del_branch.status_code == 200
    
    # 7. Delete Group
    del_group = await api_client.delete(f"/api/groups/{group_id}")
    assert del_group.status_code == 200

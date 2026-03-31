import pytest
from app.core import config
from uuid import uuid4
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_job_model_lifecycle(api_client, real_db):
    # 1. Login
    login_data = {"username": config.SUPERADMIN_USERNAME, "password": config.SUPERADMIN_PASSWORD}
    await api_client.post("/api/auth/login", json=login_data)
    
    # 2. Create Group & Branch
    group_res = await api_client.post("/api/groups", json={"name": f"JobGroup-{uuid4().hex[:4]}"})
    group_id = group_res.json()["data"]["group_id"]
    branch_res = await api_client.post("/api/branches", json={"name": f"JobBranch-{uuid4().hex[:4]}", "group_id": group_id})
    branch_id = branch_res.json()["data"]["branch_id"]
    
    # 3. Create Job (it will fail data check but still be created in DB)
    job_payload = {
        "dataset": {
            "branch_id": branch_id,
            "date_from": (datetime.utcnow() - timedelta(days=8)).isoformat(),
            "date_to": datetime.utcnow().isoformat(),
            "features": ["temp", "co2"]
        },
        "feature_engineering": {},
        "forecast": {"horizon": 24, "step_ahead": 1},
        "model_hyperparams": {}
    }
    
    response = await api_client.post("/api/jobs/create", json=job_payload)
    # The API might return 201 with status "failed" if no data, or "pending" if it bypasses check
    assert response.status_code == 201
    job_id = response.json()["data"]["job_id"]
    
    # 4. Simulate AI Server Update (this should trigger model creation)
    model_id = str(uuid4())
    update_payload = {
        "secret": response.json()["data"].get("secret") or "dummy", # We might need the real secret from DB if not returned
        "status": "completed",
        "model_id": model_id,
        "model_name": "Test LSTM Model",
        "result": {"accuracy": 0.95}
    }
    
    # Get the secret from the database since it's not returned by the API for security
    row = await real_db.fetchrow("SELECT secret FROM jobs WHERE job_id = $1", job_id)
    update_payload["secret"] = row["secret"]
    
    update_res = await api_client.post(f"/api/jobs/update/{job_id}", json=update_payload)
    assert update_res.status_code == 200
    
    # 5. Verify Model was created
    models_res = await api_client.get("/api/models")
    assert any(m["model_id"] == model_id for m in models_res.json()["data"]["items"])
    
    # 6. Verify Job status
    status_res = await api_client.get(f"/api/jobs/status/{job_id}")
    assert status_res.json()["data"]["status"] == "completed"
    assert status_res.json()["data"]["model_id"] == model_id

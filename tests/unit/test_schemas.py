import pytest
from pydantic import ValidationError
from app.schemas import LoginRequest, SensorCreateRequest, JobCreateRequest

def test_login_request_valid():
    data = {"username": "admin", "password": "password123"}
    request = LoginRequest(**data)
    assert request.username == "admin"
    assert request.password == "password123"

def test_login_request_invalid():
    with pytest.raises(ValidationError):
        LoginRequest(username="admin")  # Thiếu password

def test_sensor_create_valid():
    data = {"name": "Sensor 1", "branch_id": 10}
    request = SensorCreateRequest(**data)
    assert request.name == "Sensor 1"
    assert request.branch_id == 10

def test_job_create_minimal():
    # Test cấu trúc nested của JobCreateRequest
    data = {
        "dataset": {
            "branch_id": 1,
            "date_from": "2024-01-01T00:00:00",
            "date_to": "2024-01-08T00:00:00"
        },
        "feature_engineering": {},
        "forecast": {},
        "model_hyperparams": {}
    }
    request = JobCreateRequest(**data)
    assert request.dataset.branch_id == 1
    assert request.feature_engineering.use_occupancy is True  # Default value

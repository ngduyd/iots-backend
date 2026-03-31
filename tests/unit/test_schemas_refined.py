import pytest
from datetime import datetime
from pydantic import ValidationError
from app.schemas import (
    LoginRequest,
    SensorCreateRequest,
    CameraResponse,
    BranchCreateRequest,
    UserCreateRequest,
    JobCreateRequest,
    DatasetParams,
    FeatureEngineeringParams,
    ForecastParams,
    ModelHyperparams,
    ResponseMessage
)

def test_login_request_valid():
    data = {"username": "admin", "password": "password123"}
    model = LoginRequest(**data)
    assert model.username == "admin"
    assert model.password == "password123"

def test_login_request_invalid():
    with pytest.raises(ValidationError):
        LoginRequest(username="admin") # Missing password

def test_sensor_create_request_valid():
    data = {"name": "Sensor 1", "branch_id": 1}
    model = SensorCreateRequest(**data)
    assert model.name == "Sensor 1"
    assert model.branch_id == 1

def test_sensor_create_request_missing_branch():
    with pytest.raises(ValidationError):
        SensorCreateRequest(name="Sensor 1")

def test_camera_response_valid():
    data = {
        "camera_id": "CAM001",
        "branch_id": 1,
        "name": "Front Cam",
        "secret": "secret123",
        "activate": True,
        "status": "online",
        "created_at": "2024-03-31T10:00:00"
    }
    model = CameraResponse(**data)
    assert model.camera_id == "CAM001"
    assert isinstance(model.created_at, datetime)

def test_branch_create_request_defaults():
    data = {"group_id": 1, "name": "HCM Branch"}
    model = BranchCreateRequest(**data)
    assert model.group_id == 1
    assert model.thresholds is None
    assert model.model_id is None

def test_user_create_request_defaults():
    data = {"username": "user1", "password": "pass"}
    model = UserCreateRequest(**data)
    assert model.role == "user"

def test_job_create_request_nested():
    data = {
        "dataset": {
            "branch_id": 1,
            "date_from": "2024-01-01T00:00:00",
            "date_to": "2024-01-07T00:00:00"
        },
        "feature_engineering": {},
        "forecast": {"horizon": 24},
        "model_hyperparams": {"n_estimators": 100}
    }
    model = JobCreateRequest(**data)
    assert model.dataset.branch_id == 1
    assert model.forecast.horizon == 24
    assert model.model_hyperparams.n_estimators == 100

def test_response_message_any_data():
    # Test with dict
    msg_dict = ResponseMessage(code=200, message="OK", data={"id": 1})
    assert msg_dict.data["id"] == 1
    
    # Test with list
    msg_list = ResponseMessage(code=200, message="OK", data=[1, 2, 3])
    assert len(msg_list.data) == 3
    
    # Test with None
    msg_none = ResponseMessage(code=200, message="OK")
    assert msg_none.data is None

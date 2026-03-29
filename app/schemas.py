from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    user: str | None = None


class SensorStatus(BaseModel):
    sensor_id: str | None = None
    name: str | None = None
    branch_id: int | None = None
    status: str | None = None
    updated_at: datetime | None = None


class SensorCreateRequest(BaseModel):
    name: str | None = None
    branch_id: int


class CameraCreateRequest(BaseModel):
    name: str | None = None
    branch_id: int
    activate: bool | None = None


class CameraVerifyStreamRequest(BaseModel):
    id: str
    secret: str


class CameraResponse(BaseModel):
    camera_id: str
    branch_id: int | None = None
    name: str | None = None
    secret: str | None = None
    activate: bool = False
    status: str = "offline"
    created_at: datetime


class CameraListResponse(BaseModel):
    count: int
    items: list[CameraResponse]


class GroupCreateRequest(BaseModel):
    name: str


class GroupResponse(BaseModel):
    group_id: int
    name: str
    created_at: datetime


class BranchCreateRequest(BaseModel):
    group_id: int
    name: str
    thresholds: dict | None = None


class BranchCreateByAdminRequest(BaseModel):
    group_id: int | None = None
    name: str
    thresholds: dict | None = None


class BranchUpdateRequest(BaseModel):
    name: str | None = None
    group_id: int | None = None
    thresholds: dict | None = None


class BranchResponse(BaseModel):
    branch_id: int
    group_id: int | None = None
    name: str
    thresholds: dict | None = None
    created_at: datetime


class SensorValue(BaseModel):
    value: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
    mqtt_running: bool
    db_ready: bool


class SensorValueListResponse(BaseModel):
    sensor_id: str
    sensor_name: str | None = None
    count: int
    items: list[SensorValue]


class SensorListResponse(BaseModel):
    count: int
    items: list[SensorStatus]


class UserCreateRequest(BaseModel):
    username: str
    password: str
    group_id: int | None = None
    role: str = "user"


class UserCreateByAdminRequest(BaseModel):
    username: str
    password: str
    group_id: int | None = None
    role: str = "user"


class UserUpdateRequest(BaseModel):
    username: str | None = None
    group_id: int | None = None
    role: str | None = None
    password: str | None = None


class UserResponse(BaseModel):
    user_id: int
    group_id: int | None = None
    username: str
    role: str
    created_at: datetime


class PaginationQuery(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class ResponseMessage(BaseModel):
    code: int
    message: str
    data: Any | None = None


# --- Job System ---

class DatasetParams(BaseModel):
    branch_id: int
    date_from: datetime
    date_to: datetime
    features: list[str] = ["co2", "temp", "rh", "people"]
    targets: list[str] = ["co2", "temp", "rh"]


class FeatureEngineeringParams(BaseModel):
    lags: list[int] = [1, 2, 3, 5, 10, 20]
    rolls: list[int] = [5, 10, 20]
    use_time_features: bool = True
    use_diff_features: bool = True
    use_occupancy: bool = True
    use_interaction: bool = True


class ForecastParams(BaseModel):
    horizon: int = 15
    step_ahead: int = 10


class ModelHyperparams(BaseModel):
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.03
    subsample: float = 0.8
    colsample_bytree: float = 0.8


class JobCreateRequest(BaseModel):
    dataset: DatasetParams
    feature_engineering: FeatureEngineeringParams
    forecast: ForecastParams
    model_hyperparams: ModelHyperparams


class JobUpdateRequest(BaseModel):
    secret: str
    status: str
    result: dict | None = None
    message: str | None = None


class JobResponse(BaseModel):
    job_id: str
    branch_id: int
    user_id: int | None = None
    status: str
    message: str | None = None
    secret: str | None = None
    created_at: datetime
    updated_at: datetime
    dataset_params: dict
    feature_engineering_params: dict
    forecast_params: dict
    model_hyperparams: dict
    result: dict | None = None
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
    name: str | None = None
    status: str | None = None
    vbat: float | None = None
    updated_at: datetime | None = None


class SensorCreateRequest(BaseModel):
    name: str | None = None
    branch_id: int


class GroupCreateRequest(BaseModel):
    name: str


class GroupResponse(BaseModel):
    group_id: int
    name: str
    created_at: datetime


class BranchCreateRequest(BaseModel):
    group_id: int
    name: str
    alert: str = "none"


class BranchCreateByAdminRequest(BaseModel):
    group_id: int | None = None
    name: str
    alert: str = "none"


class BranchResponse(BaseModel):
    branch_id: int
    group_id: int | None = None
    name: str
    alert: str | None = None
    created_at: datetime


class SensorValue(BaseModel):
    value: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
    mqtt_running: bool
    db_ready: bool


class SensorValueListResponse(BaseModel):
    sensor: str
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
    username: str
    group_id: int | None = None
    role: str = "user"


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
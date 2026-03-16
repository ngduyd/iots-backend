from datetime import datetime
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    user: str | None = None


class SensorStatus(BaseModel):
    name: str
    status: str | None = None
    vbat: float | None = None
    updated_at: datetime | None = None


class SensorValue(BaseModel):
    type: str
    value: float
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


class PaginationQuery(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)

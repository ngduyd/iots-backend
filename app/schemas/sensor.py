from datetime import datetime
from pydantic import BaseModel

class SensorStatus(BaseModel):
    sensor_id: str | None = None
    name: str | None = None
    branch_id: int | None = None
    status: str | None = None
    updated_at: datetime | None = None

class SensorCreateRequest(BaseModel):
    name: str | None = None
    branch_id: int

class SensorValue(BaseModel):
    value: str
    created_at: datetime

class SensorValueListResponse(BaseModel):
    sensor_id: str
    sensor_name: str | None = None
    count: int
    items: list[SensorValue]

class SensorListResponse(BaseModel):
    count: int
    items: list[SensorStatus]

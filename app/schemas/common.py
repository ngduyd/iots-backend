from pydantic import BaseModel, Field
from typing import Any

class PaginationQuery(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)

class ResponseMessage(BaseModel):
    code: int
    message: str
    data: Any | None = None

class HealthResponse(BaseModel):
    status: str = "ok"
    mqtt_running: bool
    db_ready: bool

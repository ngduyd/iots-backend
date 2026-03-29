from datetime import datetime
from pydantic import BaseModel

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

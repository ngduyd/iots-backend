from datetime import datetime
from pydantic import BaseModel

class GroupCreateRequest(BaseModel):
    name: str

class GroupResponse(BaseModel):
    group_id: int
    name: str
    created_at: datetime

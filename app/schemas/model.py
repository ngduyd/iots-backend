from datetime import datetime
from pydantic import BaseModel

class ModelResponse(BaseModel):
    model_id: str
    group_id: int
    name: str
    created_at: datetime

class ModelUpdateRequest(BaseModel):
    name: str

class ModelListResponse(BaseModel):
    count: int
    items: list[ModelResponse]

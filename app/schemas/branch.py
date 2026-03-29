from datetime import datetime
from pydantic import BaseModel

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

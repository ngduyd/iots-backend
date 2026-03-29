from datetime import datetime
from pydantic import BaseModel

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

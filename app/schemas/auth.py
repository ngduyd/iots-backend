from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    message: str
    user: str | None = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

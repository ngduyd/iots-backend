from fastapi import APIRouter, HTTPException, Request, status

from app.schemas import LoginRequest, LoginResponse
from app.security import clear_user_session, create_user_session, verify_login

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request):
    if not verify_login(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    create_user_session(request, payload.username)
    return LoginResponse(message="Login successful", user=payload.username)


@router.post("/logout", response_model=LoginResponse)
def logout(request: Request):
    user = request.session.get("user")
    clear_user_session(request)
    return LoginResponse(message="Logout successful", user=user)

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas import LoginRequest, LoginResponse, ResponseMessage
from app.security import clear_user_session, create_user_session, verify_login

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=ResponseMessage)
def login(payload: LoginRequest, request: Request):
    if not verify_login(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    create_user_session(request, payload.username)
    return ResponseMessage(
        code=200,
        message="Login successful",
        data=LoginResponse(message="Login successful", user=payload.username),
    )


@router.post("/logout", response_model=ResponseMessage)
def logout(request: Request):
    user = request.session.get("user")
    clear_user_session(request)
    return ResponseMessage(
        code=200,
        message="Logout successful",
        data=LoginResponse(message="Logout successful", user=user),
    )

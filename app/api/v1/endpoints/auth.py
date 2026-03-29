from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.schemas.auth import LoginRequest, LoginResponse, ChangePasswordRequest
from app.schemas.common import ResponseMessage
from app.core import config, security
from app.services import user_service

router = APIRouter()

@router.post("/login", response_model=ResponseMessage)
async def login(payload: LoginRequest, request: Request, response: Response):
    user = await user_service.authenticate_user(payload.username, payload.password)

    if user is None and security.verify_login(payload.username, payload.password):
        user = await user_service.get_user_by_username(payload.username)
        if user is None:
            user = await user_service.create_user(
                username=payload.username,
                password=payload.password,
                role="superadmin",
            )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_id = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=config.SESSION_MAX_AGE_SECONDS
    )
    
    session_row = await user_service.user_repo.create_user_session(
        session_id=session_id,
        user_id=user["user_id"],
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cannot create login session",
        )

    security.create_user_session(request, session_id, payload.username)
    response.set_cookie(
        key="sid",
        value=session_id,
        max_age=config.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
    )

    return ResponseMessage(
        code=200,
        message="Login successful",
        data=LoginResponse(message="Login successful", user=payload.username),
    )

@router.post("/logout", response_model=ResponseMessage)
async def logout(request: Request, response: Response):
    user = request.session.get("user")
    session_id = request.session.get("sid") or request.cookies.get("sid")

    if session_id:
        session_row = await user_service.user_repo.get_active_user_session(str(session_id))
        if session_row is not None:
            current_user = await user_service.get_user(session_row.get("user_id"))
            if current_user is not None:
                user = current_user.get("username")
        await user_service.user_repo.revoke_user_session(str(session_id))

    security.clear_user_session(request)
    response.delete_cookie(key="session")
    response.delete_cookie(key="sid")

    return ResponseMessage(
        code=200,
        message="Logout successful",
        data=LoginResponse(message="Logout successful", user=user),
    )

@router.get("/validate", response_model=ResponseMessage)
async def validate_session(request: Request, response: Response):
    session_id = request.session.get("sid") or request.cookies.get("sid")

    if not session_id:
        security.clear_user_session(request)
        response.delete_cookie(key="session")
        response.delete_cookie(key="sid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    session_row = await user_service.user_repo.get_active_user_session(str(session_id))
    if session_row is None:
        security.clear_user_session(request)
        response.delete_cookie(key="session")
        response.delete_cookie(key="sid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    await user_service.user_repo.touch_user_session(str(session_id))
    current_user = await user_service.get_user(session_row.get("user_id"))
    return ResponseMessage(
        code=200,
        message="Session is valid",
        data=LoginResponse(
            message="Session is valid",
            user=current_user.get("username") if current_user else None,
        ),
    )

@router.post("/change-password", response_model=ResponseMessage)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(security.get_current_user_record),
):
    user = await user_service.authenticate_user(current_user["username"], payload.old_password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid old password",
        )

    success = await user_service.update_user(
        user_id=current_user["user_id"],
        password=payload.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )

    return ResponseMessage(
        code=200,
        message="Password changed successfully",
    )

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.schemas import ChangePasswordRequest, LoginRequest, LoginResponse, ResponseMessage
from app.core import config
from app.security import clear_user_session, create_user_session, get_current_user_record, verify_login
from app.services.database import (
    authenticate_user,
    create_log,
    create_user as create_user_db,
    create_user_session as create_user_session_db,
    get_active_user_session,
    get_user,
    get_user_by_username,
    revoke_user_session,
    touch_user_session,
    update_user as update_user_db,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=ResponseMessage)
async def login(payload: LoginRequest, request: Request, response: Response):
    # Check for superadmin (from env) first
    if verify_login(payload.username, payload.password):
        user = await get_user_by_username(payload.username)
    else:
        # Check standard user (from DB)
        user = await authenticate_user(payload.username, payload.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_id = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=config.SESSION_MAX_AGE_SECONDS
    )
    session_row = await create_user_session_db(
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

    create_user_session(request, session_id, payload.username)
    response.set_cookie(
        key="sid",
        value=session_id,
        max_age=config.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
    )

    await create_log(
        user_id=user["user_id"],
        action="LOGIN",
        group_id=user.get("group_id"),
        message=f"User '{payload.username}' logged in"
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
        session_row = await get_active_user_session(str(session_id))
        if session_row is not None:
            current_user = await get_user(session_row.get("user_id"))
            if current_user is not None:
                user = current_user.get("username")
        await revoke_user_session(str(session_id))

    clear_user_session(request)
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
        clear_user_session(request)
        response.delete_cookie(key="session")
        response.delete_cookie(key="sid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    session_row = await get_active_user_session(str(session_id))
    if session_row is None:
        clear_user_session(request)
        response.delete_cookie(key="session")
        response.delete_cookie(key="sid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    await touch_user_session(str(session_id))
    current_user = await get_user(session_row.get("user_id"))
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
    current_user: dict = Depends(get_current_user_record),
):
    """
    Change the password for the currently logged-in user.
    """
    # Verify old password
    user = await authenticate_user(current_user["username"], payload.old_password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid old password",
        )

    # Update to new password
    success = await update_user_db(
        user_id=current_user["user_id"],
        username=current_user["username"],
        group_id=current_user.get("group_id"),
        role=current_user.get("role"),
        password=payload.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password",
        )

    await create_log(
        user_id=current_user["user_id"],
        action="CHANGE_PASSWORD",
        group_id=current_user.get("group_id"),
        message=f"User '{current_user['username']}' changed their password"
    )

    return ResponseMessage(
        code=200,
        message="Password changed successfully",
    )
    
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.schemas import LoginRequest, LoginResponse, ResponseMessage
from app.core import config
from app.security import clear_user_session, create_user_session, verify_login
from app.services.database import (
    authenticate_user,
    create_user as create_user_db,
    create_user_session as create_user_session_db,
    get_active_user_session,
    get_user_by_username,
    revoke_user_session,
    touch_user_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=ResponseMessage)
async def login(payload: LoginRequest, request: Request):
    user = await authenticate_user(payload.username, payload.password)

    # Backward compatibility for bootstrap credentials from env.
    if user is None and verify_login(payload.username, payload.password):
        user = await get_user_by_username(payload.username)
        if user is None:
            user = await create_user_db(
                username=payload.username,
                password=payload.password,
                role="admin",
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

    create_user_session(request, payload.username)
    request.session["sid"] = session_id

    return ResponseMessage(
        code=200,
        message="Login successful",
        data=LoginResponse(message="Login successful", user=payload.username),
    )


@router.post("/logout", response_model=ResponseMessage)
async def logout(request: Request, response: Response):
    user = request.session.get("user")
    session_id = request.session.get("sid")

    if session_id:
        await revoke_user_session(str(session_id))

    clear_user_session(request)
    response.delete_cookie(key="session")

    return ResponseMessage(
        code=200,
        message="Logout successful",
        data=LoginResponse(message="Logout successful", user=user),
    )


@router.get("/validate", response_model=ResponseMessage)
async def validate_session(request: Request, response: Response):
    user = request.session.get("user")
    session_id = request.session.get("sid")

    if not user or not session_id:
        clear_user_session(request)
        response.delete_cookie(key="session")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    session_row = await get_active_user_session(str(session_id))
    if session_row is None:
        clear_user_session(request)
        response.delete_cookie(key="session")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    await touch_user_session(str(session_id))
    return ResponseMessage(
        code=200,
        message="Session is valid",
        data=LoginResponse(message="Session is valid", user=str(user)),
    )

import hmac
from fastapi import Depends, HTTPException, Request, status
from app.core import config
from app.services.database import get_active_user_session, get_user


def verify_login(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username, config.SUPERADMIN_USERNAME)
    pass_ok = hmac.compare_digest(password, config.SUPERADMIN_PASSWORD)
    return user_ok and pass_ok


def create_user_session(request: Request, session_id: str, username: str | None = None) -> None:
    request.session["sid"] = session_id
    if username is not None:
        request.session["user"] = username


def clear_user_session(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request) -> str:
    session_id = request.session.get("sid") or request.cookies.get("sid")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return str(session_id)


async def get_current_user_record(
    session_id: str = Depends(get_current_user),
) -> dict:
    session = await get_active_user_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
        )

    user = await get_user(session.get("user_id"))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current user not found",
        )
    return user


async def require_admin(current_user: dict = Depends(get_current_user_record)) -> dict:
    if current_user.get("role") not in {"admin", "superadmin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or superadmin role required",
        )
    return current_user


def is_superadmin(user: dict) -> bool:
    return user.get("role") == "superadmin"

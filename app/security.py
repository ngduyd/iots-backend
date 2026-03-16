import hmac

from fastapi import HTTPException, Request, status

from app.core import config


def verify_login(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username, config.AUTH_USERNAME)
    pass_ok = hmac.compare_digest(password, config.AUTH_PASSWORD)
    return user_ok and pass_ok


def create_user_session(request: Request, username: str) -> None:
    request.session["user"] = username


def clear_user_session(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return str(user)

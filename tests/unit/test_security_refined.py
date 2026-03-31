import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request
from app.security import (
    verify_login,
    create_user_session,
    clear_user_session,
    get_current_user,
    get_current_user_record,
    require_admin,
    is_superadmin
)
from app.core import config

# Mocking the Request object
def mock_request(session=None, cookies=None):
    request = MagicMock(spec=Request)
    request.session = session if session is not None else {}
    request.cookies = cookies if cookies is not None else {}
    return request

def test_verify_login():
    # Success case
    assert verify_login(config.SUPERADMIN_USERNAME, config.SUPERADMIN_PASSWORD) is True
    # Failure cases
    assert verify_login("wrong", config.SUPERADMIN_PASSWORD) is False
    assert verify_login(config.SUPERADMIN_USERNAME, "wrong") is False
    assert verify_login("", "") is False

def test_create_user_session():
    req = mock_request()
    create_user_session(req, "sid123", "testuser")
    assert req.session["sid"] == "sid123"
    assert req.session["user"] == "testuser"

def test_clear_user_session():
    req = mock_request(session={"sid": "123", "user": "abc"})
    clear_user_session(req)
    assert req.session == {}

def test_get_current_user_success():
    # From session
    req = mock_request(session={"sid": "sid_session"})
    assert get_current_user(req) == "sid_session"
    
    # From cookies
    req = mock_request(cookies={"sid": "sid_cookie"})
    assert get_current_user(req) == "sid_cookie"

def test_get_current_user_failure():
    req = mock_request()
    with pytest.raises(HTTPException) as exc:
        get_current_user(req)
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_user_record_success(monkeypatch):
    mock_session = {"user_id": 1, "username": "admin"}
    mock_user = {"user_id": 1, "username": "admin", "role": "admin"}
    
    async def mock_get_session(sid): return mock_session
    async def mock_get_user(uid): return mock_user
    
    monkeypatch.setattr("app.security.get_active_user_session", mock_get_session)
    monkeypatch.setattr("app.security.get_user", mock_get_user)
    
    user = await get_current_user_record("sid123")
    assert user["username"] == "admin"

@pytest.mark.asyncio
async def test_get_current_user_record_invalid_session(monkeypatch):
    async def mock_get_session(sid): return None
    monkeypatch.setattr("app.security.get_active_user_session", mock_get_session)
    
    with pytest.raises(HTTPException) as exc:
        await get_current_user_record("sid123")
    assert exc.value.status_code == 401
    assert "Session is invalid" in exc.value.detail

@pytest.mark.asyncio
async def test_require_admin_success():
    admin_user = {"role": "admin"}
    result = await require_admin(admin_user)
    assert result == admin_user
    
    superadmin_user = {"role": "superadmin"}
    result = await require_admin(superadmin_user)
    assert result == superadmin_user

@pytest.mark.asyncio
async def test_require_admin_failure():
    normal_user = {"role": "user"}
    with pytest.raises(HTTPException) as exc:
        await require_admin(normal_user)
    assert exc.value.status_code == 403

def test_is_superadmin():
    assert is_superadmin({"role": "superadmin"}) is True
    assert is_superadmin({"role": "admin"}) is False
    assert is_superadmin({"role": "user"}) is False
    assert is_superadmin({}) is False

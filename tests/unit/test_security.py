import os
import pytest
from app.security import verify_login, is_superadmin
from app.core import config

def test_verify_login_true(monkeypatch):
    monkeypatch.setattr(config, "SUPERADMIN_USERNAME", "admin")
    monkeypatch.setattr(config, "SUPERADMIN_PASSWORD", "secret")
    assert verify_login("admin", "secret") is True

def test_verify_login_false(monkeypatch):
    monkeypatch.setattr(config, "SUPERADMIN_USERNAME", "admin")
    monkeypatch.setattr(config, "SUPERADMIN_PASSWORD", "secret")
    assert verify_login("admin", "wrong") is False
    assert verify_login("wrong", "secret") is False

def test_is_superadmin_true():
    user = {"role": "superadmin"}
    assert is_superadmin(user) is True

def test_is_superadmin_false():
    user_admin = {"role": "admin"}
    user_normal = {"role": "user"}
    assert is_superadmin(user_admin) is False
    assert is_superadmin(user_normal) is False

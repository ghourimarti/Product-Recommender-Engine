from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.security import authenticate_user, create_access_token, verify_password, pwd_context

settings = get_settings()


def test_authenticate_valid_user():
    user = authenticate_user("user", "user123")
    assert user is not None
    assert user["username"] == "user"
    assert user["role"] == "user"


def test_authenticate_valid_admin():
    user = authenticate_user("admin", "admin123")
    assert user is not None
    assert user["role"] == "admin"


def test_authenticate_wrong_password():
    assert authenticate_user("user", "wrongpassword") is None


def test_authenticate_nonexistent_user():
    assert authenticate_user("ghost", "anypassword") is None


def test_authenticate_empty_credentials():
    assert authenticate_user("", "") is None


def test_verify_password_correct():
    hashed = pwd_context.hash("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    hashed = pwd_context.hash("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token_structure():
    token = create_access_token({"sub": "testuser"}, expires_delta=timedelta(minutes=30))
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # JWT has 3 parts


def test_token_contains_correct_subject():
    token = create_access_token({"sub": "testuser"}, expires_delta=timedelta(minutes=30))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "testuser"


def test_token_contains_expiry():
    token = create_access_token({"sub": "testuser"}, expires_delta=timedelta(minutes=30))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert "exp" in payload


def test_expired_token_raises():
    token = create_access_token({"sub": "testuser"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(Exception):  # JWTError
        jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

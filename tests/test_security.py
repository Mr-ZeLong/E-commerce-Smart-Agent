from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import create_access_token, get_current_user_id, verify_admin_token
from app.core.utils import utc_now


class TestCreateAccessToken:
    def test_generates_valid_jwt_with_correct_claims(self):
        token = create_access_token(user_id=42, is_admin=True)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert payload["sub"] == "42"
        assert payload["is_admin"] is True
        assert "exp" in payload
        assert "iat" in payload

        expected_expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        assert abs(payload["exp"] - expected_expire.timestamp()) < 5
        assert abs(payload["iat"] - utc_now().timestamp()) < 5


class TestGetCurrentUserId:
    def test_extracts_user_id_from_valid_token(self):
        token = create_access_token(user_id=123, is_admin=False)
        user_id = get_current_user_id(token)
        assert user_id == 123

    def test_raises_401_for_missing_token(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id("")
        assert exc_info.value.status_code == 401
        assert "Missing authentication token" in exc_info.value.detail

    def test_raises_401_for_expired_token(self):
        expired_time = utc_now() - timedelta(minutes=1)
        payload = {
            "sub": "1",
            "exp": expired_time,
            "iat": utc_now() - timedelta(hours=2),
            "is_admin": False,
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)
        assert exc_info.value.status_code == 401
        assert "Token has expired" in exc_info.value.detail

    def test_raises_401_for_invalid_signature(self):
        token = jwt.encode({"sub": "1"}, "wrong-secret", algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    def test_raises_401_for_malformed_token(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id("not.a.token")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    def test_raises_401_for_missing_sub_claim(self):
        token = jwt.encode(
            {"exp": utc_now() + timedelta(hours=1), "iat": utc_now(), "is_admin": False},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)
        assert exc_info.value.status_code == 401
        assert "missing user ID" in exc_info.value.detail


class TestVerifyAdminToken:
    def test_returns_user_id_for_admin_token(self):
        token = create_access_token(user_id=7, is_admin=True)
        user_id = verify_admin_token(token)
        assert user_id == 7

    def test_raises_403_for_non_admin_token(self):
        token = create_access_token(user_id=7, is_admin=False)
        with pytest.raises(HTTPException) as exc_info:
            verify_admin_token(token)
        assert exc_info.value.status_code == 403
        assert "Admin privileges required" in exc_info.value.detail

    def test_raises_401_for_invalid_token(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_admin_token("invalid-token")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

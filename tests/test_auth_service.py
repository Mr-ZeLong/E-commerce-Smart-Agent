from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.models.user import User
from app.services.auth_service import AuthService, create_user_token


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_success_returns_user(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_active = True
        mock_user.verify_password = MagicMock(return_value=True)

        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=mock_user))
        )

        service = AuthService()
        user = await service.authenticate_user(mock_session, "alice", "secret")

        assert user is mock_user
        mock_session.exec.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self):
        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=None))
        )

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate_user(mock_session, "nobody", "secret")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "用户名或密码错误" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_inactive_user_raises_403(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_active = False

        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=mock_user))
        )

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate_user(mock_session, "alice", "secret")

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "账号已被禁用" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_wrong_password_raises_401(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_active = True
        mock_user.verify_password = MagicMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.exec = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=mock_user))
        )

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate_user(mock_session, "alice", "wrongpass")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "用户名或密码错误" in exc_info.value.detail


class TestRegisterUser:
    @pytest.mark.asyncio
    async def test_success_creates_user(self):
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_session.exec = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=None))
        )
        mock_session.add = MagicMock()

        service = AuthService()
        with patch("app.services.auth_service.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "hashed_password"
            user = await service.register_user(
                mock_session,
                username="newuser",
                password="password123",
                email="new@example.com",
                full_name="New User",
                phone="13800138000",
            )

        assert isinstance(user, User)
        assert user.username == "newuser"
        assert user.password_hash == "hashed_password"
        assert user.email == "new@example.com"
        assert user.full_name == "New User"
        assert user.phone == "13800138000"
        assert user.is_admin is False
        assert user.is_active is True
        mock_session.add.assert_called_once_with(user)
        mock_session.begin.assert_called_once()
        mock_session.refresh.assert_awaited_once_with(user)

    @pytest.mark.asyncio
    async def test_duplicate_username_raises_400(self):
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_session.exec = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=MagicMock()))
        )

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.register_user(
                mock_session,
                username="existing",
                password="password123",
                email="new@example.com",
                full_name="New User",
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "用户名已存在" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_duplicate_email_raises_400(self):
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncMock())
        mock_session.exec = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=None)),
                MagicMock(first=MagicMock(return_value=MagicMock())),
            ]
        )

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.register_user(
                mock_session,
                username="newuser",
                password="password123",
                email="existing@example.com",
                full_name="New User",
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "邮箱已被注册" in exc_info.value.detail


class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_success_returns_user(self):
        mock_user = MagicMock(spec=User)
        mock_user.id = 42
        mock_user.username = "alice"
        mock_user.email = "alice@example.com"
        mock_user.full_name = "Alice Wang"
        mock_user.phone = "13800138000"
        mock_user.is_admin = False
        mock_user.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_user)

        service = AuthService()
        response = await service.get_user_info(mock_session, 42)

        assert response is mock_user

    @pytest.mark.asyncio
    async def test_user_not_found_raises_404(self):
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.get_user_info(mock_session, 999)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "用户不存在" in exc_info.value.detail


class TestCreateUserToken:
    def test_returns_jwt_string(self):
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.is_admin = False

        with patch("app.services.auth_service.create_access_token") as mock_create:
            mock_create.return_value = "fake.jwt.token"
            token = create_user_token(mock_user)

        assert token == "fake.jwt.token"
        mock_create.assert_called_once_with(user_id=1, is_admin=False)

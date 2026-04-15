import pytest
from fastapi import HTTPException, status

from app.models.user import User
from app.services.auth_service import AuthService


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_success_returns_user(self, db_session):
        user = User(
            username="alice",
            password_hash=User.hash_password("secret"),
            email="alice@example.com",
            full_name="Alice Wang",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        service = AuthService()
        result = await service.authenticate_user(db_session, "alice", "secret")

        assert result.id == user.id
        assert result.username == "alice"

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self, db_session):
        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate_user(db_session, "nobody", "secret")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "用户名或密码错误" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_inactive_user_raises_403(self, db_session):
        user = User(
            username="alice",
            password_hash=User.hash_password("secret"),
            email="alice@example.com",
            full_name="Alice Wang",
            is_active=False,
        )
        db_session.add(user)
        await db_session.commit()

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate_user(db_session, "alice", "secret")

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "账号已被禁用" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_wrong_password_raises_401(self, db_session):
        user = User(
            username="alice",
            password_hash=User.hash_password("secret"),
            email="alice@example.com",
            full_name="Alice Wang",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.authenticate_user(db_session, "alice", "wrongpass")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "用户名或密码错误" in exc_info.value.detail


class TestRegisterUser:
    @pytest.mark.asyncio
    async def test_success_creates_user(self, db_session):
        service = AuthService()
        user = await service.register_user(
            db_session,
            username="newuser",
            password="password123",
            email="new@example.com",
            full_name="New User",
            phone="13800138000",
        )

        assert isinstance(user, User)
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.full_name == "New User"
        assert user.phone == "13800138000"
        assert user.is_admin is False
        assert user.is_active is True
        assert user.verify_password("password123") is True

    @pytest.mark.asyncio
    async def test_duplicate_username_raises_400(self, db_session):
        existing = User(
            username="existing",
            password_hash=User.hash_password("password123"),
            email="existing@example.com",
            full_name="Existing User",
            is_active=True,
        )
        db_session.add(existing)
        await db_session.commit()

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.register_user(
                db_session,
                username="existing",
                password="password123",
                email="new@example.com",
                full_name="New User",
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "用户名已存在" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_duplicate_email_raises_400(self, db_session):
        existing = User(
            username="existing",
            password_hash=User.hash_password("password123"),
            email="existing@example.com",
            full_name="Existing User",
            is_active=True,
        )
        db_session.add(existing)
        await db_session.commit()

        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.register_user(
                db_session,
                username="newuser",
                password="password123",
                email="existing@example.com",
                full_name="New User",
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "邮箱已被注册" in exc_info.value.detail


class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_success_returns_user(self, db_session):
        user = User(
            username="alice",
            password_hash=User.hash_password("secret"),
            email="alice@example.com",
            full_name="Alice Wang",
            phone="13800138000",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None

        service = AuthService()
        response = await service.get_user_info(db_session, user.id)

        assert response.id == user.id
        assert response.username == "alice"
        assert response.email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_user_not_found_raises_404(self, db_session):
        service = AuthService()
        with pytest.raises(HTTPException) as exc_info:
            await service.get_user_info(db_session, 999999)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "用户不存在" in exc_info.value.detail

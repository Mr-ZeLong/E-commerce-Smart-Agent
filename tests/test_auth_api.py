import uuid

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.user import User


@pytest.mark.asyncio
async def test_login_success_returns_token_response(client):
    unique = uuid.uuid4().hex[:8]
    username = f"login_ok_{unique}"
    password = "password123"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password(password),
            email=f"{username}@test.com",
            full_name="Test User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    response = await client.post(
        "/api/v1/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_id"] == user_id
    assert data["username"] == username
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    unique = uuid.uuid4().hex[:8]
    username = f"login_wrong_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("correctpass"),
            email=f"{username}@test.com",
            full_name="Test User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/login",
        json={"username": username, "password": "wrongpass"},
    )
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client):
    response = await client.post(
        "/api/v1/login",
        json={"username": "nonexistent_user_xyz", "password": "anypass"},
    )
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_disabled_user_returns_403(client):
    unique = uuid.uuid4().hex[:8]
    username = f"login_disabled_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("password123"),
            email=f"{username}@test.com",
            full_name="Test User",
            is_admin=False,
            is_active=False,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/login",
        json={"username": username, "password": "password123"},
    )
    assert response.status_code == 403
    assert "账号已被禁用" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_success_creates_user_and_returns_token(client):
    unique = uuid.uuid4().hex[:8]
    username = f"register_ok_{unique}"

    response = await client.post(
        "/api/v1/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}@test.com",
            "full_name": "New User",
            "phone": "13800138000",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == username
    assert data["is_admin"] is False

    async with async_session_maker() as session:
        result = await session.exec(select(User).where(User.username == username))
        user = result.one_or_none()
        assert user is not None
        assert user.email == f"{username}@test.com"
        assert user.phone == "13800138000"


@pytest.mark.asyncio
async def test_register_duplicate_username_returns_400(client):
    unique = uuid.uuid4().hex[:8]
    username = f"register_dup_user_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("password123"),
            email=f"{username}_first@test.com",
            full_name="First User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/register",
        json={
            "username": username,
            "password": "password123",
            "email": f"{username}_second@test.com",
            "full_name": "Second User",
        },
    )
    assert response.status_code == 400
    assert "用户名已存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_400(client):
    unique = uuid.uuid4().hex[:8]
    email = f"register_dup_email_{unique}@test.com"

    async with async_session_maker() as session:
        user = User(
            username=f"first_user_{unique}",
            password_hash=User.hash_password("password123"),
            email=email,
            full_name="First User",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    response = await client.post(
        "/api/v1/register",
        json={
            "username": f"second_user_{unique}",
            "password": "password123",
            "email": email,
            "full_name": "Second User",
        },
    )
    assert response.status_code == 400
    assert "邮箱已被注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_me_valid_token_returns_user_info(client):
    unique = uuid.uuid4().hex[:8]
    username = f"me_ok_{unique}"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("password123"),
            email=f"{username}@test.com",
            full_name="Me Test",
            phone="13900139000",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = create_access_token(user_id=user.id, is_admin=False)

    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == username
    assert data["email"] == f"{username}@test.com"
    assert data["full_name"] == "Me Test"
    assert data["phone"] == "13900139000"
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_me_missing_token_returns_401(client):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token_returns_401(client):
    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401

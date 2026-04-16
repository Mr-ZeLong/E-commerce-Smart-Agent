import uuid
from unittest.mock import patch

import pytest

from app.models.user import User


@pytest.mark.asyncio
async def test_login_allows_five_requests_per_minute(client):
    """/login should allow 5 requests per minute from the same IP."""
    for i in range(5):
        response = await client.post(
            "/api/v1/login",
            json={"username": "nonexistent_user", "password": "wrongpass"},
        )
        assert response.status_code == 401, f"Request {i + 1} should return 401"

    # 6th request should be rate limited
    response = await client.post(
        "/api/v1/login",
        json={"username": "nonexistent_user", "password": "wrongpass"},
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_register_allows_five_requests_per_minute(client):
    """/register should allow 5 requests per minute from the same IP."""
    mock_user = User(
        id=1,
        username="mock",
        password_hash="hashed",
        email="mock@example.com",
        full_name="Mock User",
        is_admin=False,
    )

    with patch("app.services.auth_service.AuthService.register_user", return_value=mock_user):
        for i in range(5):
            response = await client.post(
                "/api/v1/register",
                json={
                    "username": f"ratelimit_user_{i}",
                    "password": "password123",
                    "email": f"ratelimit_{i}@example.com",
                    "full_name": "Test User",
                },
            )
            assert response.status_code == 200, (
                f"Request {i + 1} failed unexpectedly: {response.status_code}"
            )

        # 6th request should be rate limited
        response = await client.post(
            "/api/v1/register",
            json={
                "username": "ratelimit_user_final",
                "password": "password123",
                "email": "ratelimit_final@example.com",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_login_and_register_limits_are_independent(client):
    """Exhausting /login limit should not affect /register limit."""
    # Exhaust login limit
    for _ in range(6):
        await client.post(
            "/api/v1/login",
            json={"username": "nonexistent", "password": "wrongpass"},
        )

    login_response = await client.post(
        "/api/v1/login",
        json={"username": "nonexistent", "password": "wrongpass"},
    )
    assert login_response.status_code == 429
    assert "Retry-After" in login_response.headers

    mock_user = User(
        id=2,
        username="mock",
        password_hash="hashed",
        email="mock@example.com",
        full_name="Mock User",
        is_admin=False,
    )

    # Register should still work because it has a separate counter
    unique = uuid.uuid4().hex[:8]
    with patch("app.services.auth_service.AuthService.register_user", return_value=mock_user):
        register_response = await client.post(
            "/api/v1/register",
            json={
                "username": f"independent_test_{unique}",
                "password": "password123",
                "email": f"independent_{unique}@example.com",
                "full_name": "Test User",
            },
        )
        assert register_response.status_code == 200

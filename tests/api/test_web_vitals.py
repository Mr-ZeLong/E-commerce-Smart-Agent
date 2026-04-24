import pytest
from fastapi import status


class TestWebVitalsEndpoint:
    @pytest.mark.asyncio
    async def test_record_lcp_success(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "LCP",
                "value": 1.2,
                "rating": "good",
                "url": "http://localhost:5173/app",
                "user_agent": "Mozilla/5.0",
                "timestamp": "2026-04-24T12:00:00Z",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["status"] == "recorded"

    @pytest.mark.asyncio
    async def test_record_cls_success(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "CLS",
                "value": 0.05,
                "rating": "good",
                "url": "http://localhost:5173/app",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    @pytest.mark.asyncio
    async def test_record_fid_success(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "FID",
                "value": 0.02,
                "rating": "good",
                "url": "http://localhost:5173/app",
            },
        )
        assert response.status_code == status.HTTP_202_ACCEPTED

    @pytest.mark.asyncio
    async def test_invalid_metric_rejected(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "INVALID",
                "value": 1.0,
                "rating": "good",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_invalid_rating_rejected(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "LCP",
                "value": 1.0,
                "rating": "excellent",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_negative_value_rejected(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "LCP",
                "value": -1.0,
                "rating": "good",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_lcp_too_large_rejected(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "LCP",
                "value": 20.0,
                "rating": "poor",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_cls_too_large_rejected(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "CLS",
                "value": 1.5,
                "rating": "poor",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_fid_too_large_rejected(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "FID",
                "value": 6.0,
                "rating": "poor",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_url_too_long_rejected(self, client) -> None:
        response = await client.post(
            "/api/v1/metrics/web-vitals",
            json={
                "metric": "LCP",
                "value": 1.0,
                "rating": "good",
                "url": "http://localhost:5173/app" + "x" * 5000,
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

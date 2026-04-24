"""Tests for Prometheus query client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.observability.prometheus_client import (
    parse_scalar_value,
    parse_vector_values,
    query_prometheus,
    query_prometheus_range,
)


class TestQueryPrometheus:
    @pytest.mark.asyncio
    async def test_returns_parsed_results_on_success(self):
        mock_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "chat_requests_total", "agent": "order"},
                        "value": [1234567890.123, "42"],
                    }
                ],
            },
        }
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        mock_get = AsyncMock()
        mock_get.return_value = mock_response_obj

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            result = await query_prometheus("chat_requests_total")

        assert len(result) == 1
        assert result[0]["metric"]["__name__"] == "chat_requests_total"
        assert result[0]["value"] == [1234567890.123, "42"]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_disabled(self):
        with patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = False
            result = await query_prometheus("any_query")
        assert result == []

    @pytest.mark.asyncio
    async def test_handles_http_error(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            result = await query_prometheus("any_query")

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_nonsuccess_status(self):
        mock_response = {
            "status": "error",
            "errorType": "bad_data",
            "error": "invalid query",
        }
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        mock_get = AsyncMock()
        mock_get.return_value = mock_response_obj

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            result = await query_prometheus("any_query")

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_missing_data_key(self):
        mock_response = {"status": "success"}
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        mock_get = AsyncMock()
        mock_get.return_value = mock_response_obj

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            result = await query_prometheus("any_query")

        assert result == []

    @pytest.mark.asyncio
    async def test_uses_correct_url_and_params(self):
        mock_response = {"status": "success", "data": {"resultType": "vector", "result": []}}
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        mock_get = AsyncMock()
        mock_get.return_value = mock_response_obj

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            await query_prometheus("up", timeout=5.0)

        mock_get.assert_called_once_with(
            "http://prometheus:9090/api/v1/query", params={"query": "up"}
        )


class TestQueryPrometheusRange:
    @pytest.mark.asyncio
    async def test_returns_parsed_results_on_success(self):
        mock_response = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "chat_latency_seconds"},
                        "values": [
                            [1234567890.0, "0.25"],
                            [1234567900.0, "0.30"],
                        ],
                    }
                ],
            },
        }
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        mock_get = AsyncMock()
        mock_get.return_value = mock_response_obj

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            result = await query_prometheus_range(
                "chat_latency_seconds",
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "1h",
            )

        assert len(result) == 1
        assert result[0]["metric"]["__name__"] == "chat_latency_seconds"
        assert result[0]["values"] == [[1234567890.0, "0.25"], [1234567900.0, "0.30"]]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_disabled(self):
        with patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = False
            result = await query_prometheus_range(
                "any_query",
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "1h",
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_handles_http_error(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            result = await query_prometheus_range(
                "any_query",
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "1h",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_nonsuccess_status(self):
        mock_response = {
            "status": "error",
            "errorType": "bad_data",
            "error": "invalid query",
        }
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        mock_get = AsyncMock()
        mock_get.return_value = mock_response_obj

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            result = await query_prometheus_range(
                "any_query",
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "1h",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_uses_correct_url_and_params(self):
        mock_response = {"status": "success", "data": {"resultType": "matrix", "result": []}}
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_response_obj.raise_for_status = MagicMock()

        mock_get = AsyncMock()
        mock_get.return_value = mock_response_obj

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.observability.prometheus_client.httpx.AsyncClient", return_value=mock_client
        ), patch("app.observability.prometheus_client.settings") as mock_settings:
            mock_settings.PROMETHEUS_ENABLED = True
            mock_settings.PROMETHEUS_URL = "http://prometheus:9090"

            await query_prometheus_range(
                "up",
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                step="5m",
                timeout=15.0,
            )

        mock_get.assert_called_once_with(
            "http://prometheus:9090/api/v1/query_range",
            params={
                "query": "up",
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-01-01T01:00:00Z",
                "step": "5m",
            },
        )


class TestParseScalarValue:
    def test_extracts_float_from_result(self):
        result = [{"value": [1234567890.123, "42.5"]}]
        assert parse_scalar_value(result) == 42.5

    def test_extracts_integer_string(self):
        result = [{"value": [1234567890.123, "100"]}]
        assert parse_scalar_value(result) == 100.0

    def test_returns_none_for_empty_list(self):
        assert parse_scalar_value([]) is None

    def test_returns_none_for_missing_value_key(self):
        result = [{"metric": {"__name__": "test"}}]
        assert parse_scalar_value(result) is None

    def test_returns_none_for_short_value_tuple(self):
        result = [{"value": [1234567890.123]}]
        assert parse_scalar_value(result) is None

    def test_returns_none_for_non_numeric_string(self):
        result = [{"value": [1234567890.123, "not_a_number"]}]
        assert parse_scalar_value(result) is None

    def test_returns_none_for_none_value(self):
        result = [{"value": [1234567890.123, None]}]
        assert parse_scalar_value(result) is None


class TestParseVectorValues:
    def test_extracts_labeled_values_correctly(self):
        result = [
            {
                "metric": {"__name__": "chat_requests_total", "agent": "order"},
                "value": [1234567890.123, "42"],
            },
            {
                "metric": {"__name__": "chat_requests_total", "agent": "policy"},
                "value": [1234567890.456, "10"],
            },
        ]
        parsed = parse_vector_values(result)
        assert len(parsed) == 2
        assert parsed[0] == {
            "labels": {"__name__": "chat_requests_total", "agent": "order"},
            "value": 42.0,
        }
        assert parsed[1] == {
            "labels": {"__name__": "chat_requests_total", "agent": "policy"},
            "value": 10.0,
        }

    def test_returns_empty_list_for_empty_input(self):
        assert parse_vector_values([]) == []

    def test_skips_malformed_items(self):
        result = [
            {"metric": {"__name__": "missing_value"}},
            {
                "metric": {"__name__": "also_valid"},
                "value": [1234567890.123, "5"],
            },
        ]
        parsed = parse_vector_values(result)
        assert len(parsed) == 1
        assert parsed[0] == {"labels": {"__name__": "also_valid"}, "value": 5.0}

    def test_skips_non_numeric_values(self):
        result = [
            {"metric": {"__name__": "test"}, "value": [123, "not_numeric"]},
            {"metric": {"__name__": "test2"}, "value": [123, "3.14"]},
        ]
        parsed = parse_vector_values(result)
        assert len(parsed) == 1
        assert parsed[0] == {"labels": {"__name__": "test2"}, "value": 3.14}

    def test_handles_invalid_metric(self):
        result = [
            {"metric": {"__name__": "test"}, "value": [123, "not_numeric"]},
        ]
        parsed = parse_vector_values(result)
        assert len(parsed) == 0

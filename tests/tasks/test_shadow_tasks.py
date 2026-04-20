"""Tests for shadow testing Celery tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.shadow_tasks import _run_shadow_test, run_shadow_test


class TestRunShadowTest:
    """Test suite for shadow testing Celery task."""

    @pytest.mark.asyncio
    @patch("app.tasks.shadow_tasks._init_graphs")
    @patch("app.tasks.shadow_tasks.ShadowOrchestrator")
    async def test_run_shadow_test_sampled(self, mock_orchestrator_cls, mock_init_graphs):
        mock_prod_graph = MagicMock()
        mock_shadow_graph = MagicMock()
        mock_init_graphs.return_value = (mock_prod_graph, mock_shadow_graph)

        mock_orchestrator = MagicMock()
        mock_orchestrator.should_sample.return_value = True
        mock_orchestrator_cls.return_value = mock_orchestrator

        with patch(
            "app.tasks.shadow_tasks.ShadowOrchestrator.run_shadow", new_callable=AsyncMock
        ) as mock_run_shadow:
            mock_run_shadow.return_value = (
                {"result": {"intent_category": "ORDER", "answer": "Yes"}, "latency_ms": 100},
                {"result": {"intent_category": "ORDER", "answer": "Yes"}, "latency_ms": 120},
            )

            result = await _run_shadow_test("test query")

        assert result["sampled"] is True
        assert result["query"] == "test query"
        assert "comparison" in result
        assert "report" in result

    @pytest.mark.asyncio
    @patch("app.tasks.shadow_tasks.ShadowOrchestrator")
    async def test_run_shadow_test_not_sampled(self, mock_orchestrator_cls):
        mock_orchestrator = MagicMock()
        mock_orchestrator.should_sample.return_value = False
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = await _run_shadow_test("test query")

        assert result["sampled"] is False
        assert "Query not sampled for shadow testing" in result["message"]

    @pytest.mark.asyncio
    @patch("app.tasks.shadow_tasks._init_graphs")
    @patch("app.tasks.shadow_tasks.ShadowOrchestrator")
    async def test_run_shadow_test_graph_error(self, mock_orchestrator_cls, mock_init_graphs):
        mock_init_graphs.side_effect = Exception("Graph compilation failed")

        mock_orchestrator = MagicMock()
        mock_orchestrator.should_sample.return_value = True
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = await _run_shadow_test("test query")

        assert result["sampled"] is True
        assert "error" in result
        assert "Graph compilation failed" in result["error"]

    @pytest.mark.asyncio
    @patch("app.tasks.shadow_tasks._init_graphs")
    @patch("app.tasks.shadow_tasks.ShadowOrchestrator")
    async def test_run_shadow_test_intent_mismatch(self, mock_orchestrator_cls, mock_init_graphs):
        mock_prod_graph = MagicMock()
        mock_shadow_graph = MagicMock()
        mock_init_graphs.return_value = (mock_prod_graph, mock_shadow_graph)

        mock_orchestrator = MagicMock()
        mock_orchestrator.should_sample.return_value = True
        mock_orchestrator_cls.return_value = mock_orchestrator

        with patch(
            "app.tasks.shadow_tasks.ShadowOrchestrator.run_shadow", new_callable=AsyncMock
        ) as mock_run_shadow:
            mock_run_shadow.return_value = (
                {"result": {"intent_category": "ORDER", "answer": "Yes"}, "latency_ms": 100},
                {"result": {"intent_category": "REFUND", "answer": "No"}, "latency_ms": 150},
            )

            result = await _run_shadow_test("test query")

        assert result["sampled"] is True
        assert "comparison" in result
        assert "report" in result

    @pytest.mark.asyncio
    @patch("app.tasks.shadow_tasks._init_graphs")
    @patch("app.tasks.shadow_tasks.ShadowOrchestrator")
    async def test_run_shadow_test_latency_regression(
        self, mock_orchestrator_cls, mock_init_graphs
    ):
        mock_prod_graph = MagicMock()
        mock_shadow_graph = MagicMock()
        mock_init_graphs.return_value = (mock_prod_graph, mock_shadow_graph)

        mock_orchestrator = MagicMock()
        mock_orchestrator.should_sample.return_value = True
        mock_orchestrator_cls.return_value = mock_orchestrator

        with patch(
            "app.tasks.shadow_tasks.ShadowOrchestrator.run_shadow", new_callable=AsyncMock
        ) as mock_run_shadow:
            mock_run_shadow.return_value = (
                {"result": {"intent_category": "ORDER", "answer": "Yes"}, "latency_ms": 100},
                {"result": {"intent_category": "ORDER", "answer": "Yes"}, "latency_ms": 700},
            )

            result = await _run_shadow_test("test query")

        assert result["sampled"] is True
        assert "comparison" in result
        assert "report" in result

    def test_run_shadow_test_celery_task(self):
        with patch("app.tasks.shadow_tasks._run_shadow_test") as mock_run:
            mock_run.return_value = {"sampled": True, "query": "test"}
            result = run_shadow_test.run("test query")
            assert result["sampled"] is True
            mock_run.assert_called_once()

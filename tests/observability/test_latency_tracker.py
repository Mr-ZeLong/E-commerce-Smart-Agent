"""Tests for latency tracker percentile computation and DB queries."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.observability import GraphExecutionLog, GraphNodeLog
from app.models.user import User
from app.observability.latency_tracker import _compute_percentile, compute_node_latency_stats


async def _create_test_user(db_session: AsyncSession) -> int:
    user = User(
        username="obstest",
        password_hash=User.hash_password("secret"),
        email="obs@test.com",
        full_name="Obs Test",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    return user.id


class TestComputePercentile:
    """Unit tests for percentile computation."""

    def test_percentile_empty(self):
        assert _compute_percentile([], 0.5) == 0.0

    def test_percentile_single_value(self):
        assert _compute_percentile([100.0], 0.5) == 100.0

    def test_percentile_median(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert _compute_percentile(values, 0.5) == 30.0

    def test_percentile_p95(self):
        values = [float(x) for x in range(1, 101)]
        result = _compute_percentile(values, 0.95)
        assert result == pytest.approx(95.0, abs=1.0)

    def test_percentile_p99(self):
        values = [float(x) for x in range(1, 101)]
        result = _compute_percentile(values, 0.99)
        assert result == pytest.approx(99.0, abs=1.0)


@pytest.mark.asyncio
class TestComputeNodeLatencyStatsWithMocks:
    """Tests using mocks for DB session."""

    async def test_all_nodes(self):
        mock_session = AsyncMock()

        mock_row1 = MagicMock()
        mock_row1.node_name = "intent_classifier"
        mock_row1.latency_ms = 100

        mock_row2 = MagicMock()
        mock_row2.node_name = "intent_classifier"
        mock_row2.latency_ms = 200

        mock_row3 = MagicMock()
        mock_row3.node_name = "retriever"
        mock_row3.latency_ms = 500

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row1, mock_row2, mock_row3]
        mock_session.exec.return_value = mock_result

        stats = await compute_node_latency_stats(mock_session)

        assert "intent_classifier" in stats
        assert "retriever" in stats
        assert stats["intent_classifier"]["count"] == 2
        assert stats["retriever"]["count"] == 1
        assert stats["intent_classifier"]["mean_ms"] == 150.0
        assert stats["retriever"]["mean_ms"] == 500.0

    async def test_specific_node(self):
        mock_session = AsyncMock()

        mock_row1 = MagicMock()
        mock_row1.node_name = "intent_classifier"
        mock_row1.latency_ms = 100

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row1]
        mock_session.exec.return_value = mock_result

        stats = await compute_node_latency_stats(mock_session, node_name="intent_classifier")

        assert "intent_classifier" in stats
        assert stats["intent_classifier"]["count"] == 1

    async def test_empty_results(self):
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec.return_value = mock_result

        stats = await compute_node_latency_stats(mock_session)
        assert stats == {}

    async def test_db_error(self):
        mock_session = AsyncMock()
        mock_session.exec.side_effect = Exception("DB error")

        stats = await compute_node_latency_stats(mock_session)
        assert stats == {}


@pytest.mark.asyncio
class TestComputeNodeLatencyStatsWithDB:
    """Integration tests with actual database queries."""

    async def test_latency_tracker_single_node(self, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        exec_log = GraphExecutionLog(thread_id="t1", user_id=user_id)
        db_session.add(exec_log)
        await db_session.commit()
        await db_session.refresh(exec_log)

        assert exec_log.id is not None
        exec_id: int = exec_log.id

        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_a", latency_ms=100))
        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_a", latency_ms=200))
        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_a", latency_ms=300))
        await db_session.commit()

        stats = await compute_node_latency_stats(db_session)

        assert "node_a" in stats
        assert stats["node_a"]["count"] == 3
        assert stats["node_a"]["mean_ms"] == pytest.approx(200.0)
        assert stats["node_a"]["ttft_ms"] == pytest.approx(100.0)
        assert stats["node_a"]["p50_ms"] == pytest.approx(200.0)
        assert stats["node_a"]["min_ms"] == pytest.approx(100.0)
        assert stats["node_a"]["max_ms"] == pytest.approx(300.0)

    async def test_latency_tracker_multiple_nodes(self, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        exec_log = GraphExecutionLog(thread_id="t2", user_id=user_id)
        db_session.add(exec_log)
        await db_session.commit()
        await db_session.refresh(exec_log)

        assert exec_log.id is not None
        exec_id: int = exec_log.id

        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_a", latency_ms=50))
        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_b", latency_ms=150))
        await db_session.commit()

        stats = await compute_node_latency_stats(db_session)

        assert "node_a" in stats
        assert "node_b" in stats
        assert stats["node_a"]["count"] == 1
        assert stats["node_b"]["count"] == 1

    async def test_latency_tracker_filter_by_node_name(self, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        exec_log = GraphExecutionLog(thread_id="t3", user_id=user_id)
        db_session.add(exec_log)
        await db_session.commit()
        await db_session.refresh(exec_log)

        assert exec_log.id is not None
        exec_id: int = exec_log.id

        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_a", latency_ms=50))
        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_b", latency_ms=150))
        await db_session.commit()

        stats = await compute_node_latency_stats(db_session, node_name="node_a")

        assert "node_a" in stats
        assert "node_b" not in stats

    async def test_latency_tracker_percentiles(self, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        exec_log = GraphExecutionLog(thread_id="t4", user_id=user_id)
        db_session.add(exec_log)
        await db_session.commit()
        await db_session.refresh(exec_log)

        assert exec_log.id is not None
        exec_id: int = exec_log.id

        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for lat in latencies:
            db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_p", latency_ms=lat))
        await db_session.commit()

        stats = await compute_node_latency_stats(db_session)

        assert stats["node_p"]["p50_ms"] == pytest.approx(55.0)
        assert stats["node_p"]["p95_ms"] == pytest.approx(95.5)
        assert stats["node_p"]["p99_ms"] == pytest.approx(99.1)

    async def test_latency_tracker_total_ms(self, db_session: AsyncSession):
        user_id = await _create_test_user(db_session)
        exec_log = GraphExecutionLog(thread_id="t5", user_id=user_id)
        db_session.add(exec_log)
        await db_session.commit()
        await db_session.refresh(exec_log)

        assert exec_log.id is not None
        exec_id: int = exec_log.id

        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_t", latency_ms=100))
        db_session.add(GraphNodeLog(execution_id=exec_id, node_name="node_t", latency_ms=200))
        await db_session.commit()

        stats = await compute_node_latency_stats(db_session)

        assert stats["node_t"]["total_ms"] == 300.0

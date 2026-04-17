"""Tests for continuous improvement Celery tasks."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.continuous_improvement import AuditBatch, AuditSample, RootCause
from app.tasks.continuous_improvement_tasks import run_weekly_audit


class TestRunWeeklyAudit:
    """Test suite for run_weekly_audit Celery task."""

    @patch("app.tasks.continuous_improvement_tasks.async_session_maker")
    @patch("app.tasks.continuous_improvement_tasks.ContinuousImprovementService")
    def test_run_weekly_audit_success(self, mock_service_cls, mock_session_maker):
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_service = MagicMock()
        mock_service.run_audit = AsyncMock(
            return_value=AuditBatch(
                week_start="2024-01-01",
                total_conversations=1000,
                sample_size=50,
                samples=[
                    AuditSample(
                        thread_id="thread-1",
                        user_id=1,
                        intent_category="ORDER",
                        final_agent="order_agent",
                        confidence_score=0.8,
                        needs_human_transfer=False,
                        created_at=datetime.now(UTC),
                        root_cause=RootCause.INTENT_ERROR,
                    )
                ],
            )
        )
        mock_service_cls.return_value = mock_service

        result = run_weekly_audit.run()

        assert result["total_conversations"] == 1000
        assert result["sample_size"] == 50
        assert result["week_start"] == "2024-01-01"
        mock_service.run_audit.assert_called_once_with(days=7, sample_rate=0.05)

    @patch("app.tasks.continuous_improvement_tasks.async_session_maker")
    @patch("app.tasks.continuous_improvement_tasks.ContinuousImprovementService")
    def test_run_weekly_audit_empty_conversations(self, mock_service_cls, mock_session_maker):
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_service = MagicMock()
        mock_service.run_audit = AsyncMock(
            return_value=AuditBatch(
                week_start="2024-01-01",
                total_conversations=0,
                sample_size=0,
                samples=[],
            )
        )
        mock_service_cls.return_value = mock_service

        result = run_weekly_audit.run()

        assert result["total_conversations"] == 0
        assert result["sample_size"] == 0

    @patch("app.tasks.continuous_improvement_tasks.async_session_maker")
    @patch("app.tasks.continuous_improvement_tasks.ContinuousImprovementService")
    def test_run_weekly_audit_service_error(self, mock_service_cls, mock_session_maker):
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_service = MagicMock()
        mock_service.run_audit = AsyncMock(side_effect=Exception("Database connection failed"))
        mock_service_cls.return_value = mock_service

        with pytest.raises(Exception, match="Database connection failed"):
            run_weekly_audit.run()

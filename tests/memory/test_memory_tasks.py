from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.tasks.memory_tasks import extract_and_save_facts


@pytest.fixture
def mock_sync_session():
    """Return a mocked sync SQLModel session."""
    session = MagicMock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()

    def make_exec(existing_facts=None):
        exec_mock = MagicMock()
        result_mock = MagicMock()
        result_mock.one_or_none.return_value = existing_facts
        exec_mock.return_value = result_mock
        return exec_mock

    session.exec = make_exec()
    return session


def test_extract_and_save_facts_deduplicates_existing_facts(mock_sync_session):
    """Celery task should skip facts that already exist for the same thread."""
    with (
        patch("app.tasks.memory_tasks.sync_session_maker") as mock_maker,
        patch("app.tasks.memory_tasks.FactExtractor") as mock_extractor_cls,
    ):
        mock_maker.return_value.__enter__.return_value = mock_sync_session

        # Simulate async extraction returning two facts
        mock_extractor = MagicMock()
        mock_extractor_cls.return_value = mock_extractor
        mock_extractor.extract_facts = AsyncMock(
            return_value=[
                {
                    "fact_type": "preference",
                    "content": "likes fast shipping",
                    "confidence": 0.9,
                },
                {
                    "fact_type": "general",
                    "content": "is a vip",
                    "confidence": 0.8,
                },
            ]
        )

        # First fact already exists; second is new
        call_count = [0]

        def side_effect(*_args, **_kwargs):
            call_count[0] += 1
            result_mock = MagicMock()
            # first call (preference) -> existing; second call (general) -> None
            result_mock.one_or_none.return_value = Mock(id=1) if call_count[0] == 1 else None
            return result_mock

        exec_mock = MagicMock(side_effect=side_effect)
        mock_sync_session.exec = exec_mock

        result = extract_and_save_facts(
            user_id=1,
            thread_id="t1",
            history_json='[{"role":"user","content":"hi"}]',
            question="send it fast",
            answer="sure, expedited shipping available",
        )

        assert result["status"] == "success"
        assert result["facts_extracted"] == 1
        assert mock_sync_session.add.call_count == 1
        mock_sync_session.commit.assert_called_once()


def test_extract_and_save_facts_saves_all_when_no_existing_facts(mock_sync_session):
    """Celery task should save all facts when none already exist."""
    with (
        patch("app.tasks.memory_tasks.sync_session_maker") as mock_maker,
        patch("app.tasks.memory_tasks.FactExtractor") as mock_extractor_cls,
    ):
        mock_maker.return_value.__enter__.return_value = mock_sync_session

        mock_extractor = MagicMock()
        mock_extractor_cls.return_value = mock_extractor
        mock_extractor.extract_facts = AsyncMock(
            return_value=[
                {"fact_type": "preference", "content": "likes red", "confidence": 0.9},
            ]
        )

        result_mock = MagicMock()
        result_mock.one_or_none.return_value = None
        exec_mock = MagicMock(return_value=result_mock)
        mock_sync_session.exec = exec_mock

        result = extract_and_save_facts(
            user_id=1,
            thread_id="t2",
            history_json="[]",
            question="what color",
            answer="red",
        )

        assert result["status"] == "success"
        assert result["facts_extracted"] == 1
        mock_sync_session.add.assert_called_once()
        mock_sync_session.commit.assert_called_once()

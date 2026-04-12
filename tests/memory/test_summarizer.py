from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.memory.summarizer import SessionSummarizer
from app.models.state import make_agent_state


@pytest.fixture
def summarizer():
    return SessionSummarizer(llm=MagicMock())


def test_should_summarize_history_over_20(summarizer):
    state = make_agent_state(question="q", history=[{"role": "user", "content": "hi"}] * 21)
    assert summarizer.should_summarize(state) is True


def test_should_summarize_when_human_transfer(summarizer):
    state = make_agent_state(question="q", history=[], needs_human_transfer=True)
    assert summarizer.should_summarize(state) is False


def test_should_summarize_when_awaiting_clarification(summarizer):
    state = make_agent_state(question="q", history=[], awaiting_clarification=True)
    assert summarizer.should_summarize(state) is False


def test_should_summarize_natural_end_short_thread(summarizer):
    state = make_agent_state(question="q", history=[{"role": "user", "content": "hi"}] * 5)
    assert summarizer.should_summarize(state) is True


def test_should_summarize_short_thread_blocked_by_human_transfer(summarizer):
    state = make_agent_state(
        question="q",
        history=[{"role": "user", "content": "hi"}] * 5,
        needs_human_transfer=True,
    )
    assert summarizer.should_summarize(state) is False


@pytest.mark.asyncio
async def test_summarize_thread(summarizer):
    summarizer.llm.ainvoke = AsyncMock(
        return_value=MagicMock(content="The user asked about shipping.")
    )
    summary = await summarizer.summarize_thread([{"role": "user", "content": "hi"}])
    assert summary == "The user asked about shipping."


@pytest.mark.asyncio
async def test_run_persists_summary(summarizer):
    state = dict(
        make_agent_state(
            question="how long is shipping",
            user_id=1,
            thread_id="t1",
            history=[{"role": "user", "content": "how long"}] * 21,
        )
    )
    state["current_intent"] = "LOGISTICS"
    summarizer.llm.ainvoke = AsyncMock(return_value=MagicMock(content="Shipping takes 3 days."))

    mock_manager = MagicMock()
    mock_manager.save_interaction_summary = AsyncMock(return_value=MagicMock(id=100))
    summarizer.memory_manager = mock_manager

    mock_session = AsyncMock()
    result_mock = Mock()
    result_mock.one_or_none.return_value = None
    mock_session.exec.return_value = result_mock
    record = await summarizer.run(state, mock_session)

    assert record is not None
    mock_manager.save_interaction_summary.assert_awaited_once()
    call_kwargs = mock_manager.save_interaction_summary.call_args.kwargs
    assert call_kwargs["user_id"] == 1
    assert call_kwargs["thread_id"] == "t1"
    assert call_kwargs["resolved_intent"] == "LOGISTICS"


@pytest.mark.asyncio
async def test_run_summarizes_short_thread_on_natural_end(summarizer):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="natural-end-thread",
        history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    )
    summarizer.llm.ainvoke = AsyncMock(return_value=MagicMock(content="Short summary."))

    mock_manager = MagicMock()
    mock_manager.save_interaction_summary = AsyncMock(return_value=MagicMock(id=101))
    summarizer.memory_manager = mock_manager

    mock_session = AsyncMock()
    result_mock = Mock()
    result_mock.one_or_none.return_value = None
    mock_session.exec.return_value = result_mock

    record = await summarizer.run(state, mock_session)
    assert record is not None
    mock_manager.save_interaction_summary.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_skips_when_should_not_summarize(summarizer):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="t1",
        history=[],
        needs_human_transfer=True,
    )
    result = await summarizer.run(state, AsyncMock())
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_when_no_history(summarizer):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="t1",
        history=[],
    )
    result = await summarizer.run(state, AsyncMock())
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_when_missing_user_id(summarizer):
    state = make_agent_state(
        question="q",
        user_id=None,  # type: ignore
        thread_id="t1",
        history=[{"role": "user", "content": "hi"}],
    )
    summarizer.llm.ainvoke = AsyncMock(return_value=MagicMock(content="Summary."))
    result = await summarizer.run(state, AsyncMock())
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_short_thread_with_human_transfer(summarizer):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="short-thread",
        history=[{"role": "user", "content": "hi"}] * 5,
        needs_human_transfer=True,
    )
    result = await summarizer.run(state, AsyncMock())
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_when_summary_already_exists(summarizer):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="existing-thread",
        history=[{"role": "user", "content": "hi"}] * 21,
    )
    summarizer.llm.ainvoke = AsyncMock(return_value=MagicMock(content="Summary."))

    mock_session = AsyncMock()
    result_mock = Mock()
    result_mock.one_or_none.return_value = Mock(id=999)
    mock_session.exec.return_value = result_mock

    record = await summarizer.run(state, mock_session)
    assert record is None
    mock_session.exec.assert_awaited_once()

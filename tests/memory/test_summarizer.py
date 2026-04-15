import uuid

import pytest

from app.memory.summarizer import SessionSummarizer
from app.models.state import make_agent_state


@pytest.fixture
def summarizer(deterministic_llm):
    return SessionSummarizer(llm=deterministic_llm)


async def _create_test_user(session):
    from app.models.user import User

    user = User(
        username=f"test-user-{uuid.uuid4().hex}",
        email=f"{uuid.uuid4().hex}@example.com",
        full_name="Test User",
        password_hash=User.hash_password("password"),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


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
async def test_summarize_thread(summarizer, deterministic_llm):
    deterministic_llm.responses = [("Conversation messages:", "The user asked about shipping.")]
    summary = await summarizer.summarize_thread([{"role": "user", "content": "hi"}])
    assert summary == "The user asked about shipping."


@pytest.mark.asyncio
async def test_run_persists_summary(summarizer, deterministic_llm, db_session):
    user = await _create_test_user(db_session)
    thread_id = f"test-thread-{uuid.uuid4().hex}"
    state = dict(
        make_agent_state(
            question="how long is shipping",
            user_id=user.id,
            thread_id=thread_id,
            history=[{"role": "user", "content": "how long"}] * 21,
        )
    )
    state["current_intent"] = "LOGISTICS"
    deterministic_llm.responses = [("Conversation messages:", "Shipping takes 3 days.")]

    record = await summarizer.run(state, db_session)
    assert record is not None
    assert record.user_id == user.id
    assert record.thread_id == thread_id
    assert record.summary_text == "Shipping takes 3 days."
    assert record.resolved_intent == "LOGISTICS"


@pytest.mark.asyncio
async def test_run_summarizes_short_thread_on_natural_end(
    summarizer, deterministic_llm, db_session
):
    user = await _create_test_user(db_session)
    thread_id = f"test-thread-{uuid.uuid4().hex}"
    state = make_agent_state(
        question="q",
        user_id=user.id,
        thread_id=thread_id,
        history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    )
    deterministic_llm.responses = [("Conversation messages:", "Short summary.")]

    record = await summarizer.run(state, db_session)
    assert record is not None
    assert record.user_id == user.id
    assert record.thread_id == thread_id
    assert record.summary_text == "Short summary."


@pytest.mark.asyncio
async def test_run_skips_when_should_not_summarize(summarizer, db_session):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="t1",
        history=[],
        needs_human_transfer=True,
    )
    result = await summarizer.run(state, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_when_no_history(summarizer, db_session):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="t1",
        history=[],
    )
    result = await summarizer.run(state, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_when_missing_user_id(summarizer, db_session):
    state = make_agent_state(
        question="q",
        user_id=None,  # type: ignore
        thread_id="t1",
        history=[{"role": "user", "content": "hi"}],
    )
    result = await summarizer.run(state, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_short_thread_with_human_transfer(summarizer, db_session):
    state = make_agent_state(
        question="q",
        user_id=1,
        thread_id="short-thread",
        history=[{"role": "user", "content": "hi"}] * 5,
        needs_human_transfer=True,
    )
    result = await summarizer.run(state, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_run_skips_when_summary_already_exists(summarizer, deterministic_llm, db_session):
    user = await _create_test_user(db_session)
    thread_id = f"test-thread-{uuid.uuid4().hex}"
    state = make_agent_state(
        question="q",
        user_id=user.id,
        thread_id=thread_id,
        history=[{"role": "user", "content": "hi"}] * 21,
    )
    deterministic_llm.responses = [("Conversation messages:", "Summary.")]

    record = await summarizer.run(state, db_session)
    assert record is not None

    record2 = await summarizer.run(state, db_session)
    assert record2 is None

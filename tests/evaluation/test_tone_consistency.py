import pytest

from app.evaluation.tone_consistency import tone_consistency


@pytest.mark.asyncio
async def test_tone_consistency_empty_conversation():
    from unittest.mock import MagicMock

    llm = MagicMock()
    score = await tone_consistency([], llm)
    assert score == 0.0


@pytest.mark.asyncio
async def test_tone_consistency_single_turn_returns_perfect():
    from unittest.mock import MagicMock

    llm = MagicMock()
    turns = [{"role": "assistant", "content": "Hello, how can I help you?"}]
    score = await tone_consistency(turns, llm)
    assert score == 1.0


@pytest.mark.asyncio
async def test_tone_consistency_parses_score(deterministic_llm):
    deterministic_llm.responses = [("consistency", "0.85")]
    turns = [
        {"role": "assistant", "content": "Hello there."},
        {"role": "assistant", "content": "How may I assist?"},
    ]
    score = await tone_consistency(turns, deterministic_llm)
    assert score == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_tone_consistency_clamps_score(deterministic_llm):
    deterministic_llm.responses = [("consistency", "1.5")]
    turns = [
        {"role": "assistant", "content": "A"},
        {"role": "assistant", "content": "B"},
    ]
    score = await tone_consistency(turns, deterministic_llm)
    assert score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_tone_consistency_fallback_on_parse_failure(deterministic_llm):
    deterministic_llm.responses = [("consistency", "not a number")]
    turns = [
        {"role": "assistant", "content": "A"},
        {"role": "assistant", "content": "B"},
    ]
    score = await tone_consistency(turns, deterministic_llm)
    assert score == 0.0


@pytest.mark.asyncio
async def test_tone_consistency_fallback_on_exception(deterministic_llm):
    deterministic_llm.exception = RuntimeError("LLM failure")
    turns = [
        {"role": "assistant", "content": "A"},
        {"role": "assistant", "content": "B"},
    ]
    score = await tone_consistency(turns, deterministic_llm)
    assert score == 0.0


@pytest.mark.asyncio
async def test_tone_consistency_ignores_user_turns():
    from unittest.mock import MagicMock

    llm = MagicMock()
    turns = [
        {"role": "user", "content": "Question?"},
    ]
    score = await tone_consistency(turns, llm)
    assert score == 1.0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_tone_consistency(real_llm):
    turns = [
        {"role": "assistant", "content": "您好，很高兴为您服务。"},
        {"role": "assistant", "content": "请问有什么可以帮您的吗？"},
    ]
    score = await tone_consistency(turns, real_llm)
    assert 0.0 <= score <= 1.0

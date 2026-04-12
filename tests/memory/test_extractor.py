from unittest.mock import AsyncMock, MagicMock

import pytest

from app.memory.extractor import FactExtractor


@pytest.fixture
def extractor():
    return FactExtractor(llm=MagicMock())


@pytest.mark.asyncio
async def test_extract_facts_valid_json(extractor):
    extractor.llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='[{"fact_type": "preference", "content": "likes fast shipping", "confidence": 0.9}, {"fact_type": "general", "content": "is a vip", "confidence": 0.95}]'
        )
    )

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="send it fast",
        answer="sure, expedited shipping available",
    )
    assert len(facts) == 2
    assert facts[0]["fact_type"] == "preference"
    assert facts[0]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_extract_facts_markdown_wrapped(extractor):
    extractor.llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='```json\n[{"fact_type": "preference", "content": "likes blue", "confidence": 0.8}]\n```'
        )
    )

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="what color",
        answer="blue is nice",
    )
    assert len(facts) == 1
    assert facts[0]["content"] == "likes blue"


@pytest.mark.asyncio
async def test_extract_facts_invalid_json(extractor):
    extractor.llm.ainvoke = AsyncMock(return_value=MagicMock(content="not json"))

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="hi",
        answer="hello",
    )
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_non_list_response(extractor):
    extractor.llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"fact_type": "general"}'))

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="hi",
        answer="hello",
    )
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_filters_low_confidence(extractor):
    extractor.llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content='[{"fact_type": "preference", "content": "likes red", "confidence": 0.95}, {"fact_type": "general", "content": "maybe tall", "confidence": 0.5}]'
        )
    )

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="what do you like",
        answer="i like red",
    )
    assert len(facts) == 1
    assert facts[0]["content"] == "likes red"


@pytest.mark.asyncio
async def test_extract_facts_skips_credit_card_pii(extractor):
    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="my card is 4111111111111111",
        answer="ok",
    )
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_skips_password_pii(extractor):
    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="my password: secret123",
        answer="ok",
    )
    assert facts == []

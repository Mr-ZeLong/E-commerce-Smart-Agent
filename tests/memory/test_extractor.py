import pytest

from app.memory.extractor import FactExtractor


@pytest.fixture
def extractor(deterministic_llm):
    return FactExtractor(llm=deterministic_llm)


@pytest.mark.asyncio
async def test_extract_facts_valid_json(extractor, deterministic_llm):
    deterministic_llm.responses = [
        (
            "send it fast",
            '[{"fact_type": "preference", "content": "likes fast shipping", "confidence": 0.9}, {"fact_type": "general", "content": "is a vip", "confidence": 0.95}]',
        )
    ]

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
    assert facts[1]["fact_type"] == "general"
    assert facts[1]["confidence"] == 0.95


@pytest.mark.asyncio
async def test_extract_facts_markdown_wrapped(extractor, deterministic_llm):
    deterministic_llm.responses = [
        (
            "what color",
            '```json\n[{"fact_type": "preference", "content": "likes blue", "confidence": 0.8}]\n```',
        )
    ]

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
async def test_extract_facts_invalid_json(extractor, deterministic_llm):
    deterministic_llm.responses = [("not json", "not json")]

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="not json",
        answer="hello",
    )
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_empty_response(extractor, deterministic_llm):
    deterministic_llm.responses = [("empty", "")]

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="empty",
        answer="response",
    )
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_non_list_response(extractor, deterministic_llm):
    deterministic_llm.responses = [("general", '{"fact_type": "general"}')]

    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="general",
        answer="hello",
    )
    assert facts == []


@pytest.mark.asyncio
async def test_extract_facts_filters_low_confidence(extractor, deterministic_llm):
    deterministic_llm.responses = [
        (
            "what do you like",
            '[{"fact_type": "preference", "content": "likes red", "confidence": 0.95}, {"fact_type": "general", "content": "maybe tall", "confidence": 0.5}]',
        )
    ]

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
        question="my card is 123456789012345",
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


@pytest.fixture
def real_extractor(real_llm):
    return FactExtractor(llm=real_llm)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_extract_facts(real_extractor):
    facts = await real_extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="I prefer fast shipping",
        answer="We offer expedited shipping options",
    )
    assert isinstance(facts, list)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_extract_facts_chinese(real_extractor):
    facts = await real_extractor.extract_facts(
        user_id=1,
        thread_id="t1",
        history=[],
        question="我喜欢红色的商品",
        answer="我们有红色、蓝色和绿色可选",
    )
    assert isinstance(facts, list)

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.agents.supervisor import _INTENT_TO_AGENT, SupervisorAgent
from app.core.database import async_session_maker
from app.intent.multi_intent import are_independent
from app.models.state import make_agent_state
from tests._llm import DeterministicChatModel


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _clear_routing_rules():
    async with async_session_maker() as session:
        conn = await session.connection()
        await conn.execute(text("DELETE FROM routing_rules"))
        await session.commit()
    yield


@pytest.fixture
def supervisor():
    return SupervisorAgent(llm=DeterministicChatModel())


@pytest.mark.asyncio
async def test_supervisor_single_intent(supervisor):
    state = make_agent_state(
        question="运费怎么算",
        intent_result={"primary_intent": "POLICY"},
        slots={},
    )
    result = await supervisor.process(state)
    assert result["response"] == ""
    updated = result["updated_state"]
    assert updated["next_agent"] == "policy_agent"
    assert updated["execution_mode"] == "serial"
    assert "policy_agent" in updated["pending_agent_results"]


@pytest.mark.asyncio
async def test_supervisor_carts_intent(supervisor):
    state = make_agent_state(
        question="帮我加购物车",
        intent_result={"primary_intent": "CART"},
        slots={},
    )
    result = await supervisor.process(state)
    updated = result["updated_state"]
    assert updated["next_agent"] == "cart"
    assert "cart" in updated["pending_agent_results"]


@pytest.mark.asyncio
async def test_supervisor_product_intent(supervisor):
    state = make_agent_state(
        question="有没有手机壳",
        intent_result={"primary_intent": "PRODUCT"},
        slots={},
    )
    result = await supervisor.process(state)
    updated = result["updated_state"]
    assert updated["next_agent"] == "product"
    assert "product" in updated["pending_agent_results"]


@pytest.mark.asyncio
async def test_supervisor_parallel_independent_intents(supervisor):
    state = make_agent_state(
        question="查订单顺便问下退货政策",
        intent_result={"primary_intent": "ORDER"},
        slots={
            "pending_intents": [
                {"primary_intent": "POLICY"},
            ]
        },
    )
    result = await supervisor.process(state)
    updated = result["updated_state"]
    assert updated["execution_mode"] == "parallel"
    assert "order_agent" in updated["pending_agent_results"]
    assert "policy_agent" in updated["pending_agent_results"]


@pytest.mark.asyncio
async def test_supervisor_serial_dependent_intents(supervisor):
    state = make_agent_state(
        question="下单然后支付",
        intent_result={"primary_intent": "CART"},
        slots={
            "pending_intents": [
                {"primary_intent": "PAYMENT"},
            ]
        },
    )
    result = await supervisor.process(state)
    updated = result["updated_state"]
    assert updated["execution_mode"] == "serial"
    assert updated["next_agent"] == "cart"
    assert "cart" in updated["pending_agent_results"]
    assert "payment" in updated["pending_agent_results"]


def test_intent_mappings_complete():
    assert _INTENT_TO_AGENT["PRODUCT"] == "product"
    assert _INTENT_TO_AGENT["CART"] == "cart"
    assert _INTENT_TO_AGENT["ORDER"] == "order_agent"
    assert _INTENT_TO_AGENT["POLICY"] == "policy_agent"


def test_are_independent():
    assert are_independent("ORDER", "POLICY") is True
    assert are_independent("PRODUCT", "POLICY") is True
    assert are_independent("CART", "PAYMENT") is False
    assert are_independent("ORDER", "ORDER") is False

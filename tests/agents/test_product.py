import pytest

from app.agents.product import ProductAgent
from app.models.state import make_agent_state
from tests._agents import DeterministicToolRegistry


@pytest.fixture
def agent(deterministic_llm):
    registry = DeterministicToolRegistry(
        responses={
            "product": {
                "output": {
                    "status": "success",
                    "products": [
                        {
                            "name": "纯棉T恤",
                            "price": 99.0,
                            "in_stock": True,
                            "description": "舒适透气的纯棉T恤",
                        },
                        {
                            "name": "速干运动衫",
                            "price": 129.0,
                            "in_stock": False,
                            "description": "专业速干面料",
                        },
                    ],
                }
            }
        }
    )
    return ProductAgent(tool_registry=registry, llm=deterministic_llm)


@pytest.mark.asyncio
async def test_product_agent_listing(agent):
    state = make_agent_state(question="推荐几款T恤")
    result = await agent.process(state)
    assert "纯棉T恤" in result["response"]
    assert "速干运动衫" in result["response"]
    assert result["updated_state"]["product_data"]["status"] == "success"


@pytest.mark.asyncio
async def test_product_agent_not_found(deterministic_llm):
    registry = DeterministicToolRegistry(responses={"product": {"output": {"status": "not_found"}}})
    agent = ProductAgent(tool_registry=registry, llm=deterministic_llm)

    state = make_agent_state(question="找一些不存在的东西")
    result = await agent.process(state)
    assert "未找到相关商品" in result["response"]


@pytest.mark.asyncio
async def test_product_agent_direct_answer(deterministic_llm):
    registry = DeterministicToolRegistry(
        responses={
            "product": {
                "output": {
                    "status": "success",
                    "products": [
                        {
                            "name": "智能手机",
                            "price": 2999.0,
                            "in_stock": True,
                            "description": "旗舰手机",
                        }
                    ],
                    "direct_answer": "智能手机 的屏幕为 6.7英寸。",
                }
            }
        }
    )
    agent = ProductAgent(tool_registry=registry, llm=deterministic_llm)

    state = make_agent_state(question="这款手机屏幕多大")
    result = await agent.process(state)
    assert result["response"] == "智能手机 的屏幕为 6.7英寸。"


@pytest.fixture
def real_product_agent(real_llm):
    registry = DeterministicToolRegistry(
        responses={
            "product": {
                "output": {
                    "status": "success",
                    "products": [
                        {
                            "name": "纯棉T恤",
                            "price": 99.0,
                            "in_stock": True,
                            "description": "舒适透气的纯棉T恤",
                        }
                    ],
                }
            }
        }
    )
    return ProductAgent(tool_registry=registry, llm=real_llm)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_product_agent_listing(real_product_agent):
    state = make_agent_state(question="推荐几款T恤")
    result = await real_product_agent.process(state)
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0

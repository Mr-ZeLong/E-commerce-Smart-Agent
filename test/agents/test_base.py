import pytest

from app.agents.base import AgentResult, BaseAgent


class ConcreteAgent(BaseAgent):
    """测试用的具体 Agent 实现"""

    async def process(self, state: dict) -> AgentResult:
        return AgentResult(
            response="test response",
            updated_state={"test": True}
        )


class TestBaseAgent:
    """测试基础 Agent 类"""

    @pytest.fixture
    def agent(self):
        return ConcreteAgent(name="test_agent")

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """测试 Agent 初始化"""
        assert agent.name == "test_agent"
        assert agent.system_prompt is None

    @pytest.mark.asyncio
    async def test_agent_process(self, agent):
        """测试 Agent 处理逻辑"""
        result = await agent.process({"question": "test"})
        assert isinstance(result, AgentResult)
        assert result.response == "test response"
        assert result.updated_state["test"] is True

    @pytest.mark.asyncio
    async def test_agent_result_defaults(self):
        """测试 AgentResult 默认值"""
        result = AgentResult(response="hello")
        assert result.response == "hello"
        assert result.updated_state is None
        assert result.confidence is None
        assert result.needs_human is False

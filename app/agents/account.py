import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.base import BaseAgent
from app.models.state import AgentProcessResult, AgentState
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

ACCOUNT_SYSTEM_PROMPT = """你是专业的电商账户服务助手。

规则：
1. 语气友好、亲切
2. 准确展示用户账户信息、会员等级、余额和优惠券
3. 不透露敏感信息如密码
4. 严禁编造数据，所有信息必须来自工具返回结果"""


class AccountAgent(BaseAgent):
    """账户信息查询 Agent"""

    def __init__(self, tool_registry: ToolRegistry, llm: BaseChatModel):
        super().__init__(name="account", llm=llm, system_prompt=ACCOUNT_SYSTEM_PROMPT)
        self.tool_registry = tool_registry

    async def process(self, state: AgentState) -> AgentProcessResult:
        await self._load_config()
        override = await self._resolve_experiment_prompt(state)
        if override:
            self._dynamic_system_prompt = override
        tool_result = await self.tool_registry.execute("account", state)
        output = tool_result.output
        memory_prefix = self._format_memory_prefix(state.get("memory_context"))

        if output.get("error"):
            return {
                "response": memory_prefix + output["error"],
                "updated_state": {"account_data": None},
            }

        response = self._format_account_response(output)
        if memory_prefix:
            response = memory_prefix + response
        return {
            "response": response,
            "updated_state": {"account_data": output},
        }

    def _format_account_response(self, data: dict) -> str:
        username = data.get("username", "")
        full_name = data.get("full_name", "")
        email = data.get("email", "")
        phone = data.get("phone") or "未绑定"
        membership_level = data.get("membership_level", "普通会员")
        account_balance = data.get("account_balance", 0.0)
        coupons = data.get("coupons", [])

        lines = [
            f"👤 尊敬的 {full_name or username}，您好！",
            "",
            "📋 账户信息：",
            f"  用户名: {username}",
            f"  邮箱: {email}",
            f"  手机号: {phone}",
            "",
            f"🏅 会员等级: {membership_level}",
            f"💰 账户余额: ¥{account_balance:.2f}",
        ]

        if coupons:
            lines.append("")
            lines.append("🎟️ 可用优惠券：")
            for coupon in coupons:
                lines.append(
                    f"  - {coupon.get('name', '优惠券')} (有效期至 {coupon.get('expiry', 'N/A')})"
                )
        else:
            lines.append("")
            lines.append("🎟️ 当前暂无可用优惠券")

        return "\n".join(lines)

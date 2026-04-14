import logging
from datetime import datetime

from sqlmodel import select

from app.core.database import async_session_maker
from app.models.state import AgentState
from app.models.user import User
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_MEMBERSHIP_LEVELS = ["普通会员", "银卡", "金卡", "钻石"]


class AccountTool(BaseTool):
    """查询用户账户信息、会员等级、优惠券"""

    name = "account"
    description = "查询用户账户信息、会员等级、优惠券"

    async def execute(self, state: AgentState, **kwargs) -> ToolResult:
        _ = kwargs
        user_id = state.get("user_id")
        if user_id is None:
            return ToolResult(
                output={"error": "无法识别用户身份，请重新登录。"},
                confidence=1.0,
                source="account_tool",
            )

        async with async_session_maker() as session:
            result = await session.exec(select(User).where(User.id == user_id))
            user = result.one_or_none()

            if user is None:
                return ToolResult(
                    output={"error": f"未找到用户 ID {user_id} 的账户信息。"},
                    confidence=1.0,
                    source="account_tool",
                )

            membership_level = self._compute_membership_level(user)
            account_balance = self._compute_account_balance(user)
            coupons = self._compute_coupons(user)

            output = {
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "membership_level": membership_level,
                "account_balance": account_balance,
                "coupons": coupons,
            }

            return ToolResult(output=output, confidence=1.0, source="account_tool")

    def _compute_membership_level(self, user: User) -> str:
        if user.id is not None:
            index = user.id % len(_MEMBERSHIP_LEVELS)
            return _MEMBERSHIP_LEVELS[index]
        return _MEMBERSHIP_LEVELS[0]

    def _compute_account_balance(self, user: User) -> float:
        base = 128.50
        if user.id is not None:
            return round(base + (user.id * 10.25), 2)
        return base

    def _compute_coupons(self, user: User) -> list[dict[str, str]]:
        year = datetime.now().year + 1
        if user.id is not None and user.id % 2 == 0:
            return [
                {"name": "满100减10", "expiry": f"{year}-12-31"},
                {"name": "免运费券", "expiry": f"{year}-11-30"},
            ]
        return [
            {"name": "满100减10", "expiry": f"{year}-12-31"},
        ]

# app/graph/tools.py
"""
LangGraph Tools: Agent 可调用的工具函数
"""

from typing import Annotated

from langchain_core.tools import tool
from pydantic import Field

from app.services.refund_tool_service import (
    check_refund_eligibility as _check_refund_eligibility,
)
from app.services.refund_tool_service import (
    query_refund_status as _query_refund_status,
)
from app.services.refund_tool_service import (
    submit_refund_application as _submit_refund_application,
)

# ==========================================
# 工具 1: 检查退货资格
# ==========================================


@tool
async def check_refund_eligibility(
    order_sn: Annotated[str, Field(description="订单号，格式如 SN20240001")],
    user_id: Annotated[int, Field(description="当前登录用户的ID")],
) -> str:
    """
    检查订单是否符合退货条件。

    使用场景：
    - 用户询问"我的订单能退货吗？"
    - 在正式申请退货前进行资格预检

    返回：
    - 如果可以退货，返回"符合退货条件"及详细说明
    - 如果不能退货，返回拒绝原因（如：超期、已退、商品类别等）
    """
    return await _check_refund_eligibility(order_sn, user_id)


# ==========================================
# 工具 2: 提交退货申请
# ==========================================


@tool
async def submit_refund_application(
    order_sn: Annotated[str, Field(description="订单号，格式如 SN20240001")],
    user_id: Annotated[int, Field(description="当前登录用户的ID")],
    reason_detail: Annotated[str, Field(description="用户填写的退货原因详细描述")],
    reason_category: Annotated[
        str | None,
        Field(
            description="退货原因分类，可选值: "
            "QUALITY_ISSUE(质量问题), SIZE_NOT_FIT(尺码不合适), "
            "NOT_AS_DESCRIBED(与描述不符), CHANGED_MIND(不想要了), OTHER(其他)"
        ),
    ] = None,
) -> str:
    """
    提交退货申请。

    使用场景：
    - 用户明确表示"我要退货"
    - 用户已提供退货原因

    注意：
    - 此工具会自动校验退货资格
    - 如果资格不符，会直接拒绝并返回原因
    - 成功后会生成退货申请记录

    返回：
    - 成功：返回申请编号和后续流程说明
    - 失败：返回拒绝原因
    """
    return await _submit_refund_application(order_sn, user_id, reason_detail, reason_category)


# ==========================================
# 工具 3: 查询退货申请状态
# ==========================================


@tool
async def query_refund_status(
    user_id: Annotated[int, Field(description="当前登录用户的ID")],
    refund_id: Annotated[
        int | None, Field(description="退货申请编号，如果不提供则返回用户所有退货申请")
    ] = None,
) -> str:
    """
    查询退货申请状态。

    使用场景：
    - 用户询问"我的退货申请怎么样了？"
    - 用户提供申请编号查询具体状态
    - 用户想查看所有退货记录

    返回：
    - 如果指定申请编号：返回该申请的详细信息
    - 如果未指定：返回用户所有退货申请列表
    """
    return await _query_refund_status(user_id, refund_id)


# ==========================================
# 工具列表导出
# ==========================================

# 将所有工具放入列表，供 LangGraph 使用
refund_tools = [check_refund_eligibility, submit_refund_application, query_refund_status]

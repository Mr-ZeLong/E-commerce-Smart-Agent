# app/graph/nodes.py
import re
from datetime import UTC, datetime
from decimal import Decimal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from sqlmodel import select

from app.core.config import settings
from app.core.database import async_session_maker
from app.graph.state import AgentState
from app.retrieval.embeddings import embedding_model
from app.models.audit import AuditAction, AuditLog, RiskLevel
from app.models.order import Order
from app.models.refund import RefundApplication, RefundReason, RefundStatus
from app.tasks.refund_tasks import notify_admin_audit
from app.websocket.manager import manager

# ==========================================
# 全局组件初始化
# ==========================================

# 1. Embedding 模型（使用自定义适配器）已迁移至 app.retrieval.embeddings

# 2. LLM 模型 (用于生成回答)
_llm: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            base_url=settings.OPENAI_BASE_URL,  # ty:ignore[unknown-argument]
            api_key=SecretStr(settings.OPENAI_API_KEY),  # ty:ignore[unknown-argument]
            model=settings.LLM_MODEL,  # ty:ignore[unknown-argument]
            temperature=0,
        )
    return _llm

# 3. Prompt 模板
PROMPT_TEMPLATE = """
你是一个专业的电商政策咨询专家。请基于以下检索到的 context 回答用户的问题。

规则：
1. 只能依据 context 中的信息回答。
2. 如果 context 为空或没有相关信息，请直接回答"抱歉，暂未查询到相关规定"，严禁编造。
3. 语气专业、客气。

Context:
{context}

User Question:
{question}
"""

prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)

# ==========================================
# 节点函数定义
# ==========================================

# Generate 节点的 System Prompt
GENERATE_SYSTEM_PROMPT = """
你是一个电商客服助手。请根据提供的 [参考信息] 友好地回答用户。

规则：
1. 如果是订单信息，请清晰列出订单号、状态、总额和配送地址。
2. 如果是政策信息，请引用相关条款。
3. 如果参考信息为空，请礼貌地告知无法查到，并引导用户提供更多细节（如单号）。
4. 严禁编造数据库中不存在的订单状态。
"""

async def generate(state: AgentState) -> dict:
    print(" [Generate] 正在生成综合回复...")

    # 1. 组装参考信息
    context_parts = []

    # 加入政策背景
    if state.get("context"):
        context_parts.append("【相关政策】:\n" + "\n".join(state["context"]))

    # 加入订单背景
    if state.get("order_data"):
        order_raw = state["order_data"]
        if hasattr(order_raw, "model_dump"):
            order = order_raw.model_dump()  # ty:ignore[call-non-callable]
        else:
            order = order_raw or {}

        def safe_get(d, *keys, default=None):
            if not isinstance(d, dict):
                return default
            for k in keys:
                if k in d and d[k] is not None:
                    return d[k]
            return default

        order_sn = safe_get(order, "order_sn", "sn", default="未知")
        status = safe_get(order, "status", default="未知")
        amount = safe_get(order, "total_amount", "amount", default=0)
        tracking = safe_get(order, "tracking_number", "tracking", "shipping_address", default=None)
        items = safe_get(order, "items", default=[])

        order_str = (
            f"【订单详情】:\n"
            f"- 订单号: {order_sn}\n"
            f"- 当前状态: {status}\n"
            f"- 订单金额: {amount} 元\n"
            f"- 收货地址: {tracking or '暂无'}\n"
            f"- 商品明细:  {items}"
        )
        context_parts.append(order_str)

    context_info = "\n\n".join(context_parts) if context_parts else "暂无相关参考信息。"

    # 2. 构建用户消息
    user_content = f"""[参考信息]：
{context_info}

[用户问题]：
{state['question']}"""

    # 3. 调用 LLM
    messages = [
        SystemMessage(content=GENERATE_SYSTEM_PROMPT),
        HumanMessage(content=user_content)
    ]

    response = await get_llm().ainvoke(messages)

    return {"answer": response.content}


# 意图识别的 System Prompt
INTENT_PROMPT = """你是一个电商客服分类器。你的任务是根据用户的输入，将其归类为以下四种意图之一：

- "ORDER":   用户询问关于他们自己的订单状态、物流、详情等（但不是退货）。
  示例："我的订单到哪了？"、"查询订单 SN20240001"

- "POLICY":  用户询问关于平台通用的退换货、运费、时效等政策信息。
  示例："内衣可以退货吗？"、"运费怎么算？"

- "REFUND": 用户明确表示要办理退货、退款、换货等售后服务。
  示例："我要退货"、"申请退款"、"这个订单我不要了"

- "OTHER": 用户进行闲聊、打招呼或提出与上述无关的问题。
  示例："你好"、"讲个笑话"

只返回分类标签（ORDER/POLICY/REFUND/OTHER），不要返回任何其他文字。"""


async def intent_router(state: AgentState):
    """
    意图识别节点：判断用户想干什么
    """
    print(f" [Router] 正在分析意图:  {state['question']}")

    response = await get_llm().ainvoke([
        SystemMessage(content=INTENT_PROMPT),
        HumanMessage(content=state["question"])
    ])

    intent = response.content.strip().upper()  # ty:ignore[unresolved-attribute]

    # 容错处理
    if intent not in ["ORDER", "POLICY", "REFUND", "OTHER"]:
        intent = "OTHER"

    print(f" [Router] 识别结果: {intent}")
    return {"intent": intent}

async def query_order(state: AgentState):
    """
    订单查询节点：从数据库查数据
    """
    question = state["question"]
    user_id = state["user_id"]

    import re
    order_sn_match = re.search(r'SN\d+', question.upper())

    # 构造查询
    if not order_sn_match:
        print(" [QueryOrder] 获取用户最近订单")
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())  # ty:ignore[unresolved-attribute]
            .limit(1)
        )
    else:
        order_sn = order_sn_match.group()
        print(f" [QueryOrder] 查询订单号: {order_sn}")
        stmt = select(Order).where(
            Order.order_sn == order_sn,
            Order.user_id == user_id
        )

    async with async_session_maker() as session:
        result = await session.exec(stmt)
        order = result.first()

    if not order:
        return {
            "order_data": None,
            "context": ["用户询问了订单，但数据库中未查到相关记录。"]
        }

    # 组装订单信息
    items_str = ", ".join([f"{i['name']}(x{i['qty']})" for i in order.items])
    order_context = (
        f"订单号: {order.order_sn}\n"
        f"状态: {order.status}\n"
        f"商品:  {items_str}\n"
        f"金额: {order.total_amount}元\n"
        f"物流单号: {order.tracking_number or '暂无'}"
    )

    return {
        "order_data":  order.model_dump(),
        "context": [order_context]
    }


async def handle_refund(state: AgentState) -> dict:
    """
    退货流程节点：处理退货申请


    """
    print(" [Refund] 启动退货流程")

    question = state["question"]
    user_id = state["user_id"]

    # 1. 提取订单号
    order_sn_match = re.search(r'(SN\d+)', question, re.IGNORECASE)

    if not order_sn_match:
        return {
            "answer": " 请提供订单号。例如：我要退货，订单号 SN20240003",
            "refund_flow_active": False
        }

    order_sn = order_sn_match.group(1).upper()
    print(f" [Refund] 订单号: {order_sn}")

    # 2. 查询订单
    async with async_session_maker() as session:
        result = await session.execute(  # ty:ignore[deprecated]
            select(Order).where(
                Order.order_sn == order_sn,
                Order.user_id == user_id
            )
        )
        order = result.scalar_one_or_none()

        if not order:
            return {
                "answer":  f" 未找到订单 {order_sn}，请确认订单号是否正确。",
                "refund_flow_active": False
            }

        # 3. 检查订单状态
        if order.status not in ["PAID", "SHIPPED", "DELIVERED"]:
            return {
                "answer": f" 订单 {order_sn} 当前状态为 {order.status}，不符合退货条件。",
                "refund_flow_active": False
            }

        # 4. 检查商品是否可退货（简化版）
        items = order.items
        non_returnable = []
        for item in items:
            # 示例：内衣不可退货
            if "内衣" in item.get("name", ""):
                non_returnable.append(item["name"])

        if non_returnable:
            return {
                "answer": f" 该订单包含不可退货商品：{', '.join(non_returnable)}。根据平台政策，贴身衣物拆封后不支持退货。",
                "refund_flow_active": False
            }

        # 5. 提取退货原因
        reason_detail = question

        # 简单的原因分类
        if "质量" in question or "破损" in question:
            reason_category = RefundReason.QUALITY_ISSUE
        elif "尺码" in question or "大小" in question or "不合适" in question:
            reason_category = RefundReason.SIZE_NOT_FIT
        elif "不符" in question or "描述" in question:
            reason_category = RefundReason.NOT_AS_DESCRIBED
        else:
            reason_category = RefundReason.OTHER

        # 6. 创建退货申请
        refund = RefundApplication(
            order_id=order.id,
            user_id=user_id,
            status=RefundStatus.PENDING,
            reason_category=reason_category,
            reason_detail=reason_detail,
            refund_amount=order.total_amount
        )

        session.add(refund)
        await session.commit()
        await session.refresh(refund)

        print(f" [Refund] 退货申请已创建:  ID={refund.id}, Amount=¥{refund.refund_amount}")

        # 7. 返回退货数据，交给审核节点处理
        return {
            "order_data": order.model_dump(),
            "refund_data": {
                "refund_id": refund.id,
                "order_id": order.id,
                "order_sn": order_sn,
                "amount": refund.refund_amount,
                "reason": reason_detail,
                "reason_category": reason_category
            },
            "answer": "" # 留空，等待后续节点生成
        }


async def check_refund_eligibility(state: AgentState) -> dict:
    """
    v4.0 退货资格审核节点

    根据退款金额判断是否需要人工审核
    """

    print(" [Audit] 检查退货资格...")

    # 从状态中获取退款申请信息
    refund_data = state.get("refund_data")
    if not refund_data:
        # 没有退款数据，可能是其他流程，直接返回
        return {
            "audit_required": False,
            "answer": state.get("answer", "")
        }

    refund_amount = Decimal(str(refund_data.get("amount", 0)))
    refund_id = refund_data.get("refund_id")

    print(f" [Audit] 退款金额: ¥{refund_amount}")

    # 判断风险等级
    high_risk_threshold = Decimal(str(settings.HIGH_RISK_REFUND_AMOUNT))
    medium_risk_threshold = Decimal(str(settings.MEDIUM_RISK_REFUND_AMOUNT))
    if refund_amount >= high_risk_threshold:
        risk_level = RiskLevel.HIGH
        trigger_reason = f"高额退款申请：¥{refund_amount} (≥ ¥{high_risk_threshold})"
        needs_audit = True
    elif refund_amount >= medium_risk_threshold:
        risk_level = RiskLevel.MEDIUM
        trigger_reason = f"中额退款申请：¥{refund_amount} (≥ ¥{medium_risk_threshold})"
        needs_audit = True
    else:
        # 低风险，自动通过
        print(" [Audit] 低风险退款，自动通过")

        # 更新退款状态为已批准
        async with async_session_maker() as session:
            refund = await session.get(RefundApplication, refund_id)
            if refund:
                refund.status = RefundStatus.APPROVED
                refund.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
                session.add(refund)
                await session.commit()

        return {
            "audit_required":  False,
            "answer": f" 您的退货申请已自动审核通过！\n\n 申请编号:  {refund_id}\n 退款金额: ¥{refund_amount}\n\n资金将在 3-5 个工作日内原路退回，请注意查收。"
        }

    if not needs_audit:
        return {
            "audit_required": False,
            "answer": state.get("answer", "")
        }

    # 创建审计日志
    async with async_session_maker() as session:
        audit_log = AuditLog(
            thread_id=state["thread_id"],
            user_id=state["user_id"],
            order_id=refund_data.get("order_id"),
            refund_application_id=refund_id,
            trigger_reason=trigger_reason,
            risk_level=risk_level,
            action=AuditAction.PENDING,
            context_snapshot={
                "question": state["question"],
                "refund_data": refund_data,
                "order_data": state.get("order_data"),
                "history": state.get("history", []),
            }
        )
        session.add(audit_log)
        await session.commit()
        await session.refresh(audit_log)

        audit_log_id = audit_log.id
        print(f" [Audit] 审计日志已创建: ID={audit_log_id}")

    # 触发管理员通知异步任务
    try:
        notify_admin_audit.delay(audit_log_id)
        print(" [Audit] 已发送管理员通知任务")
    except Exception as e:
        print(f" [Audit] 发送通知失败: {e}")

    # 通过 WebSocket 实时通知用户
    try:
        await manager.notify_status_change(
            thread_id=state["thread_id"],
            status="WAITING_ADMIN",
            data={
                "risk_level": risk_level,
                "trigger_reason": trigger_reason,
                "audit_log_id": audit_log_id,
                "refund_amount":  refund_amount,
            }
        )
        print(" [Audit] WebSocket 通知已发送")
    except Exception as e:
        print(f" [Audit] WebSocket 通知失败: {e}")

    print(f" [Audit] 需要人工审核 - {risk_level} - {trigger_reason}")

    return {
        "audit_required": True,
        "audit_log_id": audit_log_id,
        "answer":  f" 您的退货申请需要人工审核\n\n 申请编号: {refund_id}\n 退款金额: ¥{refund_amount}\n 风险等级: {risk_level}\n 触发原因: {trigger_reason}\n\n我们将在 24 小时内完成审核，请耐心等待。您可以关闭页面，稍后返回查看结果。"
    }

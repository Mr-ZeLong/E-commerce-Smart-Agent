# type: ignore
"""
管理员 API
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from opentelemetry import trace
from sqlalchemy import case, func, text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.core.utils import utc_now
from app.models.message import MessageCard
from app.models.observability import GraphExecutionLog
from app.schemas.admin import (
    AdminDecisionRequest,
    AdminDecisionResponse,
    AuditTask,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationThreadResponse,
    TaskStatsResponse,
)
from app.services.admin_service import AdminService, AuditAlreadyProcessedError, AuditNotFoundError

router = APIRouter()
tracer = trace.get_tracer(__name__)


def get_admin_service(request: Request) -> AdminService:
    return AdminService(manager=request.app.state.manager)


@router.get("/admin/tasks", response_model=list[AuditTask])
async def get_pending_tasks(
    risk_level: str | None = None,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(get_admin_service),
):
    """获取待审核任务列表"""
    with tracer.start_as_current_span("admin_get_pending_tasks") as span:
        span.set_attribute("admin.user_id", current_admin_id)
        span.set_attribute("admin.risk_level", risk_level or "all")
        return await service.get_pending_tasks(session, risk_level)


@router.get("/admin/confidence-tasks", response_model=list[AuditTask])
async def get_confidence_pending_tasks(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(get_admin_service),
):
    """获取置信度触发的待审核任务"""
    with tracer.start_as_current_span("admin_get_confidence_tasks") as span:
        span.set_attribute("admin.user_id", current_admin_id)
        return await service.get_confidence_pending_tasks(session)


@router.get("/admin/tasks-all", response_model=TaskStatsResponse)
async def get_all_pending_tasks(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(get_admin_service),
):
    """获取所有待审核任务（风险 + 置信度 + 手动）"""
    with tracer.start_as_current_span("admin_get_all_tasks") as span:
        span.set_attribute("admin.user_id", current_admin_id)
        return await service.get_all_pending_tasks(session)


@router.post("/admin/resume/{audit_log_id}", response_model=AdminDecisionResponse)
async def admin_decision(
    audit_log_id: int,
    request: AdminDecisionRequest,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
    service: AdminService = Depends(get_admin_service),
):
    """管理员决策接口"""
    with tracer.start_as_current_span("admin_decision") as span:
        span.set_attribute("admin.user_id", current_admin_id)
        span.set_attribute("admin.audit_log_id", audit_log_id)
        span.set_attribute("admin.action", request.action)
        try:
            return await service.process_admin_decision(
                session, audit_log_id, request.action, request.admin_comment, current_admin_id
            )
        except AuditNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found",
            )
        except AuditAlreadyProcessedError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This audit has already been processed",
            )


@router.get("/admin/evaluation/dataset")
async def get_evaluation_dataset(
    limit: int = 20,
    offset: int = 0,
    current_admin_id: int = Depends(get_admin_user_id),
):
    """Return paginated golden dataset records."""
    import json
    from pathlib import Path

    path = Path("tests/evaluation/golden_dataset_v1.jsonl")
    records: list[dict] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))

    total = len(records)
    paginated = records[offset : offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": paginated,
    }


@router.post("/admin/evaluation/run")
async def run_evaluation(
    http_request: Request,
    current_admin_id: int = Depends(get_admin_user_id),
):
    """Trigger offline evaluation against the golden dataset."""
    from app.evaluation.pipeline import EvaluationPipeline

    pipeline = EvaluationPipeline(
        intent_service=http_request.app.state.intent_service,
        llm=http_request.app.state.llm,
        graph=http_request.app.state.app_graph,
    )
    results = await pipeline.run("tests/evaluation/golden_dataset_v1.jsonl")
    return results


@router.get("/admin/metrics/sessions")
async def get_session_metrics(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """会话统计：24h / 7d / 30d 的 execution 数量"""
    now = utc_now()
    ranges = {
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
    }
    result = {}
    for label, since in ranges.items():
        count_result = await session.exec(
            select(func.count()).where(GraphExecutionLog.created_at >= since)
        )
        result[label] = count_result.one()
    return result


@router.get("/admin/metrics/transfers")
async def get_transfer_metrics(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """人工转接率：按 final_agent 分组统计"""
    total_result = await session.exec(
        select(GraphExecutionLog.final_agent, func.count()).group_by(GraphExecutionLog.final_agent)
    )
    transfer_result = await session.exec(
        select(GraphExecutionLog.final_agent, func.count())
        .where(GraphExecutionLog.needs_human_transfer.is_(True))
        .group_by(GraphExecutionLog.final_agent)
    )

    totals = {row[0]: row[1] for row in total_result.all()}
    transfers = {row[0]: row[1] for row in transfer_result.all()}

    metrics = []
    for agent, total in totals.items():
        metrics.append(
            {
                "final_agent": agent,
                "total": total,
                "transfers": transfers.get(agent, 0),
                "transfer_rate": round(transfers.get(agent, 0) / total, 4) if total else 0.0,
            }
        )
    return metrics


@router.get("/admin/metrics/confidence")
async def get_confidence_metrics(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """平均置信度：按 final_agent 分组"""
    result = await session.exec(
        select(
            GraphExecutionLog.final_agent,
            func.avg(GraphExecutionLog.confidence_score).label("avg_confidence"),
        )
        .where(GraphExecutionLog.confidence_score.is_not(None))
        .group_by(GraphExecutionLog.final_agent)
    )
    return [
        {"final_agent": row[0], "avg_confidence": round(row[1], 4) if row[1] else None}
        for row in result.all()
    ]


@router.get("/admin/metrics/latency")
async def get_latency_metrics(
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """P99 节点延迟：按 node_name 分组（使用 PostgreSQL PERCENTILE_CONT）"""
    stmt = text(
        """
        SELECT
            node_name,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_latency_ms
        FROM graph_node_logs
        GROUP BY node_name
        """
    )
    result = await session.exec(stmt)
    return [
        {
            "node_name": row["node_name"],
            "p99_latency_ms": round(row["p99_latency_ms"], 2) if row["p99_latency_ms"] else None,
        }
        for row in result.mappings().all()
    ]


@router.get("/admin/conversations", response_model=ConversationListResponse)
async def get_conversations(
    user_id: int | None = None,
    intent_category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    offset: int = 0,
    limit: int = 20,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    with tracer.start_as_current_span("admin_get_conversations") as span:
        span.set_attribute("admin.user_id", current_admin_id)
        span.set_attribute("admin.filter.user_id", user_id or "all")
        span.set_attribute("admin.filter.intent_category", intent_category or "all")

        conditions = []
        if start_date:
            from datetime import datetime

            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            conditions.append(MessageCard.created_at >= start_dt)
        if end_date:
            from datetime import datetime

            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            conditions.append(MessageCard.created_at <= end_dt)

        intent_thread_stmt = None
        if intent_category:
            intent_thread_stmt = (
                select(GraphExecutionLog.thread_id)
                .where(GraphExecutionLog.intent_category == intent_category)
                .distinct()
            )

        count_stmt = select(func.count(func.distinct(MessageCard.thread_id)))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        if user_id is not None:
            count_stmt = count_stmt.where(
                MessageCard.thread_id.in_(
                    select(MessageCard.thread_id)
                    .where(
                        MessageCard.sender_id == user_id,
                        MessageCard.sender_type == "user",
                    )
                    .distinct()
                )
            )
        if intent_thread_stmt is not None:
            count_stmt = count_stmt.where(MessageCard.thread_id.in_(intent_thread_stmt))
        total_result = await session.exec(count_stmt)
        total = total_result.one() or 0

        thread_stmt = (
            select(
                MessageCard.thread_id,
                func.count(MessageCard.id).label("message_count"),
                func.max(MessageCard.created_at).label("last_updated"),
                func.min(case((MessageCard.sender_type == "user", MessageCard.sender_id))).label(
                    "user_id"
                ),
            )
            .group_by(MessageCard.thread_id)
            .order_by(func.max(MessageCard.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        if conditions:
            thread_stmt = thread_stmt.where(*conditions)
        if user_id is not None:
            thread_stmt = thread_stmt.where(
                MessageCard.thread_id.in_(
                    select(MessageCard.thread_id)
                    .where(
                        MessageCard.sender_id == user_id,
                        MessageCard.sender_type == "user",
                    )
                    .distinct()
                )
            )
        if intent_thread_stmt is not None:
            thread_stmt = thread_stmt.where(MessageCard.thread_id.in_(intent_thread_stmt))

        result = await session.exec(thread_stmt)
        rows = result.all()

        thread_ids = [row[0] for row in rows]
        intent_map: dict[str, str | None] = {}
        if thread_ids:
            intent_stmt = (
                select(GraphExecutionLog.thread_id, GraphExecutionLog.intent_category)
                .where(GraphExecutionLog.thread_id.in_(thread_ids))
                .distinct()
            )
            intent_result = await session.exec(intent_stmt)
            for tid, icat in intent_result.all():
                intent_map[tid] = icat

        threads = [
            ConversationThreadResponse(
                thread_id=row[0],
                user_id=row[3],
                message_count=row[1],
                last_updated=row[2].isoformat() if row[2] else "",
                intent_category=intent_map.get(row[0]),
            )
            for row in rows
        ]

        return ConversationListResponse(threads=threads, total=total, offset=offset, limit=limit)


@router.get("/admin/conversations/{thread_id}", response_model=list[ConversationMessageResponse])
async def get_conversation_messages(
    thread_id: str,
    current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    with tracer.start_as_current_span("admin_get_conversation_messages") as span:
        span.set_attribute("admin.user_id", current_admin_id)
        span.set_attribute("admin.thread_id", thread_id)

        stmt = (
            select(MessageCard)
            .where(MessageCard.thread_id == thread_id)
            .order_by(MessageCard.created_at.asc())
        )
        result = await session.exec(stmt)
        messages = result.all()

        return [
            ConversationMessageResponse(
                id=msg.id,
                thread_id=msg.thread_id,
                sender_type=msg.sender_type,
                sender_id=msg.sender_id,
                content=msg.content,
                message_type=msg.message_type,
                created_at=msg.created_at.isoformat() if msg.created_at else "",
                meta_data=msg.meta_data,
            )
            for msg in messages
        ]

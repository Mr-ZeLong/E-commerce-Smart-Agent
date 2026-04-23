"""
管理员 API
"""

import os
import shutil
import uuid
from datetime import timedelta
from typing import cast

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from opentelemetry import trace
from sqlalchemy import case, func, text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.admin.agent_config import router as agent_config_router
from app.api.v1.admin.alerts import router as alerts_router
from app.api.v1.admin.analytics import router as analytics_router
from app.api.v1.admin.complaints import router as complaints_router
from app.api.v1.admin.evaluation_dashboard import router as evaluation_dashboard_router
from app.api.v1.admin.experiments import router as experiments_router
from app.api.v1.admin.feedback import router as feedback_router
from app.api.v1.admin.metrics_dashboard import router as metrics_dashboard_router
from app.api.v1.admin.review_queue import router as review_queue_router
from app.api.v1.admin.token_usage import router as token_usage_router
from app.core.config import settings
from app.core.database import get_session
from app.core.security import get_admin_user_id
from app.core.utils import utc_now
from app.models.knowledge_document import KnowledgeDocument
from app.models.message import MessageCard
from app.models.observability import GraphExecutionLog
from app.schemas.admin import (
    AdminDecisionRequest,
    AdminDecisionResponse,
    AuditTask,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationThreadResponse,
    KnowledgeDocumentResponse,
    KnowledgeUploadResponse,
    SyncStatusResponse,
    TaskStatsResponse,
)
from app.services.admin_service import AdminService, AuditAlreadyProcessedError, AuditNotFoundError
from app.tasks.knowledge_tasks import sync_knowledge_document

router = APIRouter()
router.include_router(agent_config_router, prefix="/admin/agents")
router.include_router(alerts_router, prefix="/admin/alerts")
router.include_router(complaints_router, prefix="/admin/complaints")
router.include_router(experiments_router, prefix="/admin/experiments")
router.include_router(feedback_router, prefix="/admin/feedback")
router.include_router(analytics_router, prefix="/admin/analytics")
router.include_router(metrics_dashboard_router, prefix="/admin/metrics")
router.include_router(evaluation_dashboard_router, prefix="/admin/evaluation")
router.include_router(token_usage_router, prefix="/admin/token-usage")
router.include_router(review_queue_router, prefix="/admin/review-queue")
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
        except AuditNotFoundError as _err:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found",
            ) from _err
        except AuditAlreadyProcessedError as _err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This audit has already been processed",
            ) from _err


@router.get("/admin/evaluation/dataset")
async def get_evaluation_dataset(
    limit: int = 20,
    offset: int = 0,
    _current_admin_id: int = Depends(get_admin_user_id),
):
    """Return paginated golden dataset records."""
    import json
    from pathlib import Path

    path = Path("data/golden_dataset_v2.jsonl")
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
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Trigger offline evaluation against the golden dataset."""
    from app.evaluation.pipeline import EvaluationPipeline

    pipeline = EvaluationPipeline(
        intent_service=http_request.app.state.intent_service,
        llm=http_request.app.state.llm,
        graph=http_request.app.state.app_graph,
        db_session=session,
    )
    results = await pipeline.run("data/golden_dataset_v2.jsonl")
    return results


@router.post("/admin/continuous-improvement/audit")
async def trigger_continuous_improvement_audit(
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Trigger a weekly quality audit for continuous improvement."""
    from app.services.continuous_improvement import ContinuousImprovementService

    service = ContinuousImprovementService(db_session=session)
    batch = await service.run_audit(days=7, sample_rate=0.05)
    return {
        "week_start": batch.week_start,
        "total_conversations": batch.total_conversations,
        "sample_size": batch.sample_size,
        "message": "Weekly audit complete. Review samples and annotate root causes.",
    }


@router.post("/admin/shadow-test/run")
async def trigger_shadow_test(
    query: str,
    _current_admin_id: int = Depends(get_admin_user_id),
):
    """Trigger a shadow test for a given query."""
    from app.tasks.shadow_tasks import run_shadow_test

    result = run_shadow_test.delay(query)
    return {
        "task_id": result.id,
        "query": query,
        "message": "Shadow test triggered asynchronously.",
    }


@router.get("/admin/metrics/sessions")
async def get_session_metrics(
    _current_admin_id: int = Depends(get_admin_user_id),
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
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """人工转接率：按 final_agent 分组统计"""
    total_result = await session.exec(
        select(GraphExecutionLog.final_agent, func.count()).group_by(GraphExecutionLog.final_agent)
    )
    transfer_result = await session.exec(
        select(GraphExecutionLog.final_agent, func.count())
        .where(GraphExecutionLog.needs_human_transfer.is_(True))  # type: ignore
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
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    """平均置信度：按 final_agent 分组"""
    result = await session.exec(
        select(
            GraphExecutionLog.final_agent,
            func.avg(GraphExecutionLog.confidence_score).label("avg_confidence"),
        )
        .where(GraphExecutionLog.confidence_score.is_not(None))  # type: ignore
        .group_by(GraphExecutionLog.final_agent)
    )
    return [
        {"final_agent": row[0], "avg_confidence": round(row[1], 4) if row[1] else None}
        for row in result.all()
    ]


@router.get("/admin/metrics/latency")
async def get_latency_metrics(
    _current_admin_id: int = Depends(get_admin_user_id),
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
    result = await session.exec(stmt)  # type: ignore
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
                MessageCard.thread_id.in_(  # type: ignore
                    select(MessageCard.thread_id)
                    .where(
                        MessageCard.sender_id == user_id,
                        MessageCard.sender_type == "user",
                    )
                    .distinct()
                )
            )
        if intent_thread_stmt is not None:
            count_stmt = count_stmt.where(MessageCard.thread_id.in_(intent_thread_stmt))  # type: ignore
        total_result = await session.exec(count_stmt)
        total = total_result.one() or 0

        thread_stmt = (
            select(
                MessageCard.thread_id,
                func.count(MessageCard.id).label("message_count"),  # type: ignore
                func.max(MessageCard.created_at).label("last_updated"),
                func.min(case((MessageCard.sender_type == "user", MessageCard.sender_id))).label(  # type: ignore
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
                MessageCard.thread_id.in_(  # type: ignore
                    select(MessageCard.thread_id)
                    .where(
                        MessageCard.sender_id == user_id,
                        MessageCard.sender_type == "user",
                    )
                    .distinct()
                )
            )
        if intent_thread_stmt is not None:
            thread_stmt = thread_stmt.where(MessageCard.thread_id.in_(intent_thread_stmt))  # type: ignore

        result = await session.exec(thread_stmt)
        rows = result.all()

        thread_ids = [row[0] for row in rows]
        intent_map: dict[str, str | None] = {}
        if thread_ids:
            intent_stmt = (
                select(GraphExecutionLog.thread_id, GraphExecutionLog.intent_category)
                .where(GraphExecutionLog.thread_id.in_(thread_ids))  # type: ignore
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
            .order_by(MessageCard.created_at.asc())  # type: ignore
        )
        result = await session.exec(stmt)
        messages = result.all()

        return [
            ConversationMessageResponse(
                id=cast(int, msg.id),
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


UPLOAD_DIR = settings.KNOWLEDGE_UPLOAD_DIR


@router.get("/admin/knowledge", response_model=list[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(
        select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())  # type: ignore
    )
    docs = result.all()
    return [
        KnowledgeDocumentResponse(
            id=cast(int, d.id),
            filename=d.filename,
            content_type=d.content_type,
            doc_size_bytes=d.doc_size_bytes,
            sync_status=d.sync_status,
            sync_message=d.sync_message,
            last_synced_at=d.last_synced_at.isoformat() if d.last_synced_at else None,
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )
        for d in docs
    ]


@router.post("/admin/knowledge", response_model=KnowledgeUploadResponse)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    storage_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = os.path.join(UPLOAD_DIR, storage_name)

    with open(storage_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size = os.path.getsize(storage_path)

    doc = KnowledgeDocument(
        filename=file.filename or "unnamed",
        storage_path=storage_path,
        content_type=file.content_type or "application/octet-stream",
        doc_size_bytes=size,
        sync_status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    assert doc.id is not None

    task = sync_knowledge_document.delay(doc.id)

    return KnowledgeUploadResponse(
        id=doc.id,
        filename=doc.filename,
        sync_status=doc.sync_status,
        task_id=task.id,
    )


@router.delete("/admin/knowledge/{doc_id}")
async def delete_knowledge_document(
    doc_id: int,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    doc = result.one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)

    await session.delete(doc)
    await session.commit()

    return {"success": True, "message": "Document deleted"}


@router.post("/admin/knowledge/{doc_id}/sync", response_model=KnowledgeUploadResponse)
async def sync_knowledge_document_endpoint(
    doc_id: int,
    _current_admin_id: int = Depends(get_admin_user_id),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    doc = result.one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    assert doc.id is not None
    task = sync_knowledge_document.delay(doc.id)

    return KnowledgeUploadResponse(
        id=doc.id,
        filename=doc.filename,
        sync_status="running",
        task_id=task.id,
    )


@router.get("/admin/knowledge/sync/{task_id}", response_model=SyncStatusResponse)
async def get_knowledge_sync_status(
    task_id: str,
    _current_admin_id: int = Depends(get_admin_user_id),
):
    from app.celery_app import celery_app

    task_result = celery_app.AsyncResult(task_id)
    return SyncStatusResponse(
        task_id=task_id,
        status=task_result.status,
        result=task_result.result if task_result.ready() else None,
    )

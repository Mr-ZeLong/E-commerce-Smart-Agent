# app/api/v1/chat.py
import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.context import tracing_v2_enabled
from langgraph.types import Command
from opentelemetry import propagate, trace
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import desc, select

from app.api.v1.chat_utils import create_stream_metadata_message
from app.api.v1.schemas import ChatRequest
from app.context.pii_filter import log_pii_detection, pii_filter
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.limiter import check_user_rate_limit, limiter
from app.core.security import get_current_user_id
from app.core.tracing import build_llm_config
from app.core.utils import build_thread_id, utc_now
from app.models.memory import AgentConfigVersion
from app.models.state import make_agent_state
from app.observability.execution_logger import log_graph_execution, log_graph_node
from app.observability.metrics import (
    record_chat_error,
    record_chat_latency,
    record_chat_request,
    record_confidence_score,
    record_context_utilization,
    record_human_transfer,
    record_node_latency,
    record_token_usage,
)
from app.observability.token_tracker import TokenTracker
from app.services.experiment_assigner import ExperimentAssigner
from app.services.online_eval import OnlineEvalService
from app.services.review_queue import ReviewQueueService
from app.tasks.observability_tasks import log_chat_observability

router = APIRouter()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


async def _maybe_create_review_ticket(
    session: Any,
    thread_id: str,
    user_id: int,
    final_state: dict[str, Any],
    intent_category: str | None,
) -> None:
    confidence = final_state.get("confidence_score")
    needs_transfer = final_state.get("needs_human_transfer", False)
    transfer_reason = final_state.get("transfer_reason")
    is_complaint = intent_category == "COMPLAINT"

    service = ReviewQueueService(session)
    risk_score, risk_factors = await service.compute_risk_score(
        confidence=confidence,
        safety_blocked=needs_transfer,
        refund_amount=None,
        is_complaint=is_complaint,
    )

    if risk_score >= 0.5:
        try:
            await service.create_ticket(
                conversation_id=thread_id,
                user_id=user_id,
                risk_score=risk_score,
                risk_factors=risk_factors,
                confidence_score=confidence,
                transfer_reason=transfer_reason,
            )
        except (SQLAlchemyError, OperationalError):
            logger.exception("Failed to create review ticket for thread %s", thread_id)


async def _safe_vector_upsert(
    vector_manager: Any,
    user_id: int,
    thread_id: str,
    message_role: str,
    content: str,
    timestamp: str,
    intent: str | None = None,
) -> None:
    """Fire-and-forget wrapper for vector upsert with error logging."""
    try:
        await vector_manager.upsert_message(
            user_id=user_id,
            thread_id=thread_id,
            message_role=message_role,
            content=content,
            timestamp=timestamp,
            intent=intent,
        )
    except (OperationalError, OSError):
        logger.exception("Failed to upsert message to vector memory")


async def _log_post_chat_metrics(
    thread_id: str,
    user_id: int,
    final_state: dict[str, Any],
    node_latencies: dict[str, int],
    variant_id: int | None,
    total_latency_ms: int,
    langsmith_run_url: str | None,
    intent_category: str | None,
    query_text: str,
    variant_llm_model: str | None,
) -> None:
    """Persist chat execution logs and metrics after the SSE stream ends.

    This function is designed to be called via asyncio.create_task so it
    does not block closing the HTTP connection.
    """
    try:
        async with async_session_maker() as session:
            final_agent_name = final_state.get("current_agent")
            version_id = await _resolve_agent_config_version_id(
                session, final_agent_name, utc_now()
            )
            execution_id = await log_graph_execution(
                session=session,
                thread_id=thread_id,
                user_id=user_id,
                intent_category=intent_category,
                final_agent=final_agent_name,
                confidence_score=final_state.get("confidence_score"),
                needs_human_transfer=bool(final_state.get("needs_human_transfer", False)),
                total_latency_ms=total_latency_ms,
                agent_config_version_id=version_id,
                context_tokens=final_state.get("context_tokens"),
                context_utilization=final_state.get("context_utilization"),
                langsmith_run_url=langsmith_run_url,
                query=query_text,
            )
            for node_name, latency_ms in node_latencies.items():
                await log_graph_node(
                    session=session,
                    execution_id=execution_id,
                    node_name=node_name,
                    latency_ms=latency_ms,
                )

            if variant_id is not None:
                try:
                    from app.models.experiment import ExperimentMetrics

                    metrics = ExperimentMetrics(
                        variant_id=variant_id,
                        user_id=user_id,
                        session_id=thread_id,
                        latency_ms=total_latency_ms,
                        token_count=final_state.get("context_tokens"),
                        confidence_score=final_state.get("confidence_score"),
                        needs_human_transfer=bool(final_state.get("needs_human_transfer", False)),
                    )
                    session.add(metrics)
                    await session.commit()
                except SQLAlchemyError:
                    logger.exception("Failed to record experiment metrics")
                    await session.rollback()

            # Risk-based routing: auto-create review ticket for high-risk conversations
            await _maybe_create_review_ticket(
                session=session,
                thread_id=thread_id,
                user_id=user_id,
                final_state=final_state,
                intent_category=intent_category,
            )

            # Persist detailed token usage to database for cost tracking
            if final_state.get("context_tokens") is not None:
                try:
                    token_tracker = TokenTracker(session)
                    response_text = final_state.get("answer", "")
                    estimated_output_tokens = max(1, len(response_text) // 4)
                    await token_tracker.log_usage(
                        user_id=user_id,
                        thread_id=thread_id,
                        agent_type=final_agent_name or "unknown",
                        input_tokens=int(final_state.get("context_tokens", 0)),
                        output_tokens=estimated_output_tokens,
                        query_text=query_text,
                        model_name=variant_llm_model or settings.LLM_MODEL,
                    )
                except (SQLAlchemyError, OperationalError):
                    logger.exception("Failed to log token usage to database")
    except Exception:
        logger.exception("Background post-chat metrics logging failed")


async def _run_shadow_in_background(
    request: Request,
    query: str,
    thread_id: str,
    user_id: int,
    production_result: dict[str, Any],
) -> None:
    """Run shadow graph in background and store comparison results.

    This function is designed to be called via asyncio.create_task so it
    does not block the SSE response.
    """
    from app.core.config import settings
    from app.evaluation.shadow import ShadowOrchestrator

    if not settings.SHADOW_TESTING_ENABLED:
        return

    orchestrator = ShadowOrchestrator(sample_rate=settings.SHADOW_SAMPLE_RATE)
    if not orchestrator.should_sample(thread_id):
        return

    shadow_graph = getattr(request.app.state, "shadow_app_graph", None)
    if shadow_graph is None:
        logger.debug("Shadow graph not initialized; skipping shadow test for thread %s", thread_id)
        return

    app_graph = request.app.state.app_graph
    try:
        prod_result, shadow_result = await ShadowOrchestrator.run_shadow(
            query=query,
            production_graph=app_graph,
            shadow_graph=shadow_graph,
            session_id=f"shadow-{thread_id}",
        )

        comparison = ShadowOrchestrator.compare_results(
            thread_id=thread_id,
            production_result=prod_result,
            shadow_result=shadow_result,
        )

        llm = getattr(request.app.state, "llm", None)
        if llm is not None:
            comparison = await ShadowOrchestrator.compare_with_llm(comparison, llm)

        from app.core.database import async_session_maker

        async with async_session_maker() as db:
            await ShadowOrchestrator.store_result(
                comparison=comparison,
                user_id=user_id,
                query=query,
                db_session=db,
            )
    except (RuntimeError, OSError):
        logger.exception("Background shadow test failed for thread %s", thread_id)


@router.post("/chat")
@limiter.limit("60/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    """
    聊天接口：支持订单查询和政策咨询

    - ORDER:  查询用户自己的订单
    - POLICY: 从知识库检索政策信息

    v4.1 更新：流式响应结束时发送置信度元数据
    """
    app_graph = request.app.state.app_graph
    if app_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is not fully initialized. Please try again in a moment.",
        )

    thread_id = build_thread_id(current_user_id, chat_request.thread_id)

    # Per-user rate limiting: 10 requests/minute before LLM calls
    # Reuse the shared Redis client from app state to avoid connection churn.
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is not None:
        await check_user_rate_limit(
            redis_client, current_user_id, max_requests=10, window_seconds=60
        )

    # Real-time PII filtering: redact sensitive data before any LLM or storage operations
    pii_result = await pii_filter.afilter_text(chat_request.question)
    filtered_question = pii_result.redacted_text
    if pii_result.has_pii:
        log_pii_detection(
            user_id=current_user_id,
            thread_id=thread_id,
            source="chat_input",
            detections=pii_result.detections,
        )

    with tracer.start_as_current_span("chat_endpoint") as span:
        span.set_attribute("chat.user_id", current_user_id)
        span.set_attribute("chat.thread_id", thread_id)

        span_context = span.get_span_context()
        otel_trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None

        async def event_generator():

            # Intent result for LangSmith metadata and observability
            # Check Redis cache first to avoid redundant LLM calls for identical queries.
            intent_service = getattr(request.app.state, "intent_service", None)
            intent_category = None
            cache_manager = getattr(request.app.state, "cache_manager", None)
            if cache_manager is not None:
                cached_intent = await cache_manager.get_intent(filtered_question)
                if cached_intent is not None:
                    intent_category = cached_intent.get("primary_intent")
            if intent_category is None and intent_service is not None:
                intent_result = await intent_service.recognize(
                    query=filtered_question,
                    session_id=thread_id,
                    conversation_history=None,
                )
                intent_category = intent_result.primary_intent.value if intent_result else None
                if cache_manager is not None and intent_category is not None:
                    await cache_manager.set_intent(
                        filtered_question,
                        {"primary_intent": intent_category},
                    )

            record_chat_request(intent_category=intent_category)

            config: RunnableConfig = build_llm_config(
                user_id=current_user_id,
                thread_id=thread_id,
                intent=intent_category,
                extra_metadata={"trace_id": otel_trace_id},
                tags=["chat_endpoint", "user_visible"],
            )
            config["configurable"] = {"thread_id": thread_id}

            variant_id: int | None = None
            memory_context_config: dict[str, Any] | None = None
            variant_llm_model: str | None = None
            variant_retriever_top_k: int | None = None
            variant_reranker_enabled: bool | None = None
            async with async_session_maker() as db:
                assigner = ExperimentAssigner()
                variant_config = await assigner.assign_with_config(
                    str(current_user_id), "agent_prompt", db=db
                )
                if variant_config is not None:
                    variant_id = variant_config.variant_id
                    memory_context_config = variant_config.memory_context_config
                    variant_llm_model = variant_config.llm_model
                    variant_retriever_top_k = variant_config.retriever_top_k
                    variant_reranker_enabled = variant_config.reranker_enabled

            initial_state = make_agent_state(
                question=filtered_question,
                user_id=current_user_id,
                thread_id=thread_id,
                history=[{"role": "user", "content": filtered_question}],
                experiment_variant_id=variant_id,
                memory_context_config=memory_context_config,
                variant_llm_model=variant_llm_model,
                variant_retriever_top_k=variant_retriever_top_k,
                variant_reranker_enabled=variant_reranker_enabled,
            )

            vector_manager = getattr(request.app.state, "vector_manager", None)
            if vector_manager is not None:
                # Fire-and-forget vector upsert to avoid blocking the SSE stream.
                asyncio.create_task(
                    _safe_vector_upsert(
                        vector_manager=vector_manager,
                        user_id=current_user_id,
                        thread_id=thread_id,
                        message_role="user",
                        content=filtered_question,
                        timestamp=utc_now().isoformat(),
                        intent=intent_category,
                    )
                )

            # v4.1: 用于收集最终状态中的置信度信息
            final_state = {}
            sent_answers: set[str] = set()
            final_answer = ""

            # Execution logging instrumentation
            start_time = time.time()
            node_start_times: dict[str, float] = {}
            node_latencies: dict[str, int] = {}

            # LangSmith tracing: wrap the graph execution to capture trace URL
            langsmith_run_url: str | None = None

            try:
                with tracing_v2_enabled(project_name=settings.LANGSMITH_PROJECT) as cb:
                    async for event in app_graph.astream_events(
                        initial_state, config, version="v2"
                    ):
                        kind = event["event"]

                        # Track node start times for latency logging
                        if kind == "on_chain_start":
                            metadata = event.get("metadata", {})
                            langgraph_node = metadata.get("langgraph_node", "")
                            if langgraph_node:
                                node_start_times[event.get("run_id", "")] = time.time()

                        # 处理 LLM 流式输出 - 只处理用户可见的 Agent 输出
                        if kind == "on_chat_model_stream":
                            # 过滤内部调用（置信度评估、意图识别等）
                            metadata = event.get("metadata", {})
                            langgraph_node = metadata.get("langgraph_node", "")
                            tags = metadata.get("tags", []) or event.get("tags", [])

                            # 只转发标记为 user_visible 的输出
                            # 过滤掉 router 和内部置信度评估的调用
                            is_internal = (
                                langgraph_node == "router_node"
                                or "confidence_eval" in tags
                                or "internal" in tags
                            )

                            if is_internal:
                                continue

                            # 只处理用户可见的 LLM 输出
                            if "user_visible" not in tags:
                                continue

                            data = event.get("data")
                            if data and isinstance(data, dict):
                                chunk = data.get("chunk")
                                if chunk:
                                    content = chunk.content
                                    if content:
                                        payload = json.dumps({"token": content}, ensure_ascii=False)
                                        yield f"data: {payload}\n\n"

                        # v4.1: 捕获 on_chain_end 事件获取最终状态
                        elif kind == "on_chain_end":
                            raw_output = event.get("data", {}).get("output", {})
                            metadata = event.get("metadata", {})
                            langgraph_node = metadata.get("langgraph_node", "")

                            # Track node latency
                            run_id = event.get("run_id", "")
                            if run_id in node_start_times and langgraph_node:
                                latency_ms = int((time.time() - node_start_times[run_id]) * 1000)
                                node_latencies[langgraph_node] = (
                                    node_latencies.get(langgraph_node, 0) + latency_ms
                                )
                                record_node_latency(
                                    node_name=langgraph_node,
                                    latency_seconds=latency_ms / 1000.0,
                                )
                                del node_start_times[run_id]

                            # LangGraph 1.1+ returns Command objects for nodes that use Command;
                            # unwrap the update dict so answer/confidence fields are accessible.
                            if isinstance(raw_output, Command):
                                output = raw_output.update
                            elif isinstance(raw_output, dict):
                                output = raw_output
                            else:
                                output = {}

                            if output:
                                # 从 router/policy/order/logistics/account/payment 节点获取 answer 发送给用户
                                # (对于 OrderAgent 等非 LLM 节点，answer 直接来自 state)
                                if (
                                    langgraph_node
                                    in (
                                        "router_node",
                                        "policy_agent",
                                        "order_agent",
                                        "logistics",
                                        "account",
                                        "payment",
                                        "product",
                                        "cart",
                                        "synthesis_node",
                                    )
                                    and "answer" in output
                                ):
                                    answer = output["answer"]
                                    if isinstance(answer, dict):
                                        answer = json.dumps(answer, ensure_ascii=False)
                                    if answer and answer not in sent_answers:
                                        sent_answers.add(answer)
                                        final_answer = answer
                                        payload = json.dumps({"token": answer}, ensure_ascii=False)
                                        yield f"data: {payload}\n\n"

                                # 收集置信度相关信息
                                if "confidence_score" in output:
                                    final_state["confidence_score"] = output["confidence_score"]
                                if "confidence_signals" in output:
                                    final_state["confidence_signals"] = output["confidence_signals"]
                                if "needs_human_transfer" in output:
                                    final_state["needs_human_transfer"] = output[
                                        "needs_human_transfer"
                                    ]
                                if "transfer_reason" in output:
                                    final_state["transfer_reason"] = output["transfer_reason"]
                                if "audit_level" in output:
                                    final_state["audit_level"] = output["audit_level"]
                                if "current_agent" in output:
                                    final_state["current_agent"] = output["current_agent"]
                                if "context_tokens" in output:
                                    final_state["context_tokens"] = output["context_tokens"]
                                if "context_utilization" in output:
                                    final_state["context_utilization"] = output[
                                        "context_utilization"
                                    ]

                    # Capture LangSmith trace URL after graph execution completes
                    if cb is not None:
                        try:
                            langsmith_run_url = cb.get_run_url()
                        except Exception:
                            logger.debug("Failed to get LangSmith run URL", exc_info=True)

                # v4.1: 在 [DONE] 之前发送元数据消息（如果存在）
                if final_state and final_state.get("confidence_score") is not None:
                    metadata = create_stream_metadata_message(
                        confidence_score=final_state.get("confidence_score"),
                        confidence_signals=final_state.get("confidence_signals"),
                        needs_human_transfer=final_state.get("needs_human_transfer"),
                        transfer_reason=final_state.get("transfer_reason"),
                        audit_level=final_state.get("audit_level"),
                    )
                    metadata_payload = json.dumps(metadata, ensure_ascii=False)
                    yield f"data: {metadata_payload}\n\n"

                if otel_trace_id:
                    yield f"data: {json.dumps({'type': 'metadata', 'trace_id': otel_trace_id}, ensure_ascii=False)}\n\n"

                yield "data: [DONE]\n\n"

                total_latency_ms = int((time.time() - start_time) * 1000)
                final_agent_name = final_state.get("current_agent")

                # Fire-and-forget vector upsert for assistant message to unblock connection close.
                if vector_manager is not None and final_answer:
                    asyncio.create_task(
                        _safe_vector_upsert(
                            vector_manager=vector_manager,
                            user_id=current_user_id,
                            thread_id=thread_id,
                            message_role="assistant",
                            content=final_answer,
                            timestamp=utc_now().isoformat(),
                            intent=intent_category,
                        )
                    )

                # Record Prometheus metrics synchronously (very fast, no I/O).
                record_chat_latency(
                    latency_seconds=total_latency_ms / 1000.0,
                    final_agent=final_agent_name,
                )
                if final_state.get("confidence_score") is not None:
                    record_confidence_score(float(final_state["confidence_score"]))
                if final_state.get("needs_human_transfer"):
                    record_human_transfer(reason=final_state.get("transfer_reason") or "unknown")
                if final_state.get("context_utilization") is not None:
                    record_context_utilization(float(final_state["context_utilization"]))
                if final_state.get("context_tokens") is not None:
                    record_token_usage(
                        tokens=int(final_state["context_tokens"]),
                        agent=final_agent_name,
                    )

                # Move all post-streaming DB writes to a Celery task so the HTTP
                # connection can be closed immediately after [DONE].
                # Propagate OTel trace context so the Celery task creates a child span.
                trace_context: dict[str, str] = {}
                propagate.inject(trace_context)
                log_chat_observability.delay(
                    thread_id=thread_id,
                    user_id=current_user_id,
                    intent_category=intent_category,
                    final_state=final_state,
                    node_latencies=node_latencies,
                    total_latency_ms=total_latency_ms,
                    chat_request_question=chat_request.question,
                    variant_id=variant_id,
                    variant_llm_model=variant_llm_model,
                    langsmith_run_url=langsmith_run_url,
                    trace_context=trace_context,
                )

                # Trigger shadow testing in background without blocking response
                asyncio.create_task(
                    _run_shadow_in_background(
                        request=request,
                        query=chat_request.question,
                        thread_id=thread_id,
                        user_id=current_user_id,
                        production_result={
                            "result": final_state,
                            "latency_ms": total_latency_ms,
                        },
                    )
                )

            except asyncio.CancelledError:
                logger.info("[Chat] Client disconnected (CancelledError)")
                raise
            except (ConnectionResetError, BrokenPipeError):
                logger.info("[Chat] Client disconnected during SSE streaming")
                return
            except (RuntimeError, OSError):
                logger.exception("[Chat] Unhandled error during SSE streaming")
                record_chat_error(error_type="runtime")
                error_payload = json.dumps(
                    {"error": "聊天服务出现内部错误，请稍后重试。"},
                    ensure_ascii=False,
                )
                yield f"data: {error_payload}\n\n"
                if otel_trace_id:
                    yield f"data: {json.dumps({'type': 'metadata', 'trace_id': otel_trace_id}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        async def _timed_event_generator():
            """Wrap event generator with global timeout to prevent hanging requests."""
            try:
                async for chunk in event_generator():
                    yield chunk
            except TimeoutError:
                logger.warning("[Chat] Request timed out after 15s")
                record_chat_error(error_type="timeout")
                error_payload = json.dumps(
                    {"error": "服务响应超时，请稍后重试或联系人工客服。"},
                    ensure_ascii=False,
                )
                yield f"data: {error_payload}\n\n"
                yield "data: [DONE]\n\n"

        headers = {}
        if otel_trace_id:
            headers["X-Trace-ID"] = otel_trace_id
        return StreamingResponse(
            _timed_event_generator(), media_type="text/event-stream", headers=headers
        )


_feedback_service = OnlineEvalService()


async def _resolve_agent_config_version_id(
    session, agent_name: str | None, before_time
) -> int | None:
    if not agent_name:
        return None
    result = await session.exec(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_name == agent_name)
        .where(AgentConfigVersion.created_at <= before_time)
        .order_by(desc(AgentConfigVersion.created_at))
        .limit(1)
    )
    version = result.one_or_none()
    return version.id if version else None


class SubmitFeedbackRequest(BaseModel):
    thread_id: str
    message_index: int
    sentiment: str
    comment: str | None = None
    category: str | None = None
    agent_type: str | None = None
    confidence_score: float | None = None


@router.post("/feedback")
async def submit_feedback(
    request: SubmitFeedbackRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    async with async_session_maker() as session:
        feedback = await _feedback_service.submit_feedback(
            db=session,
            user_id=current_user_id,
            thread_id=request.thread_id,
            message_index=request.message_index,
            sentiment=request.sentiment,
            comment=request.comment,
            category=request.category,
            agent_type=request.agent_type,
            confidence_score=request.confidence_score,
        )
    return {
        "success": True,
        "feedback_id": feedback.id,
        "score": feedback.score,
    }

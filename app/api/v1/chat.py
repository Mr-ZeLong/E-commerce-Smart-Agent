# app/api/v1/chat.py
import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from opentelemetry import trace

from app.api.v1.chat_utils import create_stream_metadata_message
from app.api.v1.schemas import ChatRequest
from app.core.database import async_session_maker
from app.core.security import get_current_user_id
from app.core.utils import build_thread_id
from app.models.state import make_agent_state
from app.observability.execution_logger import log_graph_execution, log_graph_node

router = APIRouter()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@router.post("/chat")
async def chat(
    chat_request: ChatRequest,
    http_request: Request,
    current_user_id: int = Depends(get_current_user_id),
):
    """
    聊天接口：支持订单查询和政策咨询

    - ORDER:  查询用户自己的订单
    - POLICY: 从知识库检索政策信息

    v4.1 更新：流式响应结束时发送置信度元数据
    """
    app_graph = http_request.app.state.app_graph
    if app_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is not fully initialized. Please try again in a moment.",
        )

    thread_id = build_thread_id(current_user_id, chat_request.thread_id)
    with tracer.start_as_current_span("chat_endpoint") as span:
        span.set_attribute("chat.user_id", current_user_id)
        span.set_attribute("chat.thread_id", thread_id)

        async def event_generator():
            # OTel trace ID for correlation with LangSmith
            current_span = trace.get_current_span()
            span_context = current_span.get_span_context()
            otel_trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None

            # Intent result for LangSmith metadata and observability
            intent_service = getattr(http_request.app.state, "intent_service", None)
            intent_category = None
            if intent_service is not None:
                intent_result = await intent_service.recognize(
                    query=chat_request.question,
                    session_id=thread_id,
                    conversation_history=None,
                )
                intent_category = intent_result.primary_intent.value if intent_result else None

            config: RunnableConfig = {
                "configurable": {"thread_id": thread_id},
                "metadata": {
                    "thread_id": thread_id,
                    "user_id": current_user_id,
                    "intent_result": intent_category,
                    "trace_id": otel_trace_id,
                },
            }

            initial_state = make_agent_state(
                question=chat_request.question,
                user_id=current_user_id,
                thread_id=thread_id,
            )

            # v4.1: 用于收集最终状态中的置信度信息
            final_state = {}
            sent_answers: set[str] = set()

            # Execution logging instrumentation
            start_time = time.time()
            node_start_times: dict[str, float] = {}
            node_latencies: dict[str, int] = {}

            try:
                async for event in app_graph.astream_events(initial_state, config, version="v2"):
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
                        tags = metadata.get("tags", [])

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
                        output = event.get("data", {}).get("output", {})
                        metadata = event.get("metadata", {})
                        langgraph_node = metadata.get("langgraph_node", "")

                        # Track node latency
                        run_id = event.get("run_id", "")
                        if run_id in node_start_times and langgraph_node:
                            latency_ms = int((time.time() - node_start_times[run_id]) * 1000)
                            node_latencies[langgraph_node] = (
                                node_latencies.get(langgraph_node, 0) + latency_ms
                            )
                            del node_start_times[run_id]

                        if output and isinstance(output, dict):
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
                                )
                                and "answer" in output
                            ):
                                answer = output["answer"]
                                if answer and answer not in sent_answers:
                                    sent_answers.add(answer)
                                    payload = json.dumps({"token": answer}, ensure_ascii=False)
                                    yield f"data: {payload}\n\n"

                            # 收集置信度相关信息
                            if "confidence_score" in output:
                                final_state["confidence_score"] = output["confidence_score"]
                            if "confidence_signals" in output:
                                final_state["confidence_signals"] = output["confidence_signals"]
                            if "needs_human_transfer" in output:
                                final_state["needs_human_transfer"] = output["needs_human_transfer"]
                            if "transfer_reason" in output:
                                final_state["transfer_reason"] = output["transfer_reason"]
                            if "audit_level" in output:
                                final_state["audit_level"] = output["audit_level"]
                            if "current_agent" in output:
                                final_state["current_agent"] = output["current_agent"]

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

                yield "data: [DONE]\n\n"

                # Log execution metrics asynchronously after streaming completes
                total_latency_ms = int((time.time() - start_time) * 1000)
                async with async_session_maker() as session:
                    execution_id = await log_graph_execution(
                        session=session,
                        thread_id=thread_id,
                        user_id=current_user_id,
                        intent_category=intent_category,
                        final_agent=final_state.get("current_agent"),
                        confidence_score=final_state.get("confidence_score"),
                        needs_human_transfer=bool(final_state.get("needs_human_transfer", False)),
                        total_latency_ms=total_latency_ms,
                    )
                    for node_name, latency_ms in node_latencies.items():
                        await log_graph_node(
                            session=session,
                            execution_id=execution_id,
                            node_name=node_name,
                            latency_ms=latency_ms,
                        )

            except asyncio.CancelledError:
                logger.info("[Chat] Client disconnected (CancelledError)")
                raise
            except (ConnectionResetError, BrokenPipeError):
                logger.info("[Chat] Client disconnected during SSE streaming")
                return
            except Exception:
                logger.exception("[Chat] Unhandled error during SSE streaming")
                error_payload = json.dumps(
                    {"error": "聊天服务出现内部错误，请稍后重试。"},
                    ensure_ascii=False,
                )
                yield f"data: {error_payload}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

# app/api/v1/chat.py
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig

from app.api.v1.chat_utils import create_stream_metadata_message
from app.api.v1.schemas import ChatRequest
from app.api.v1.utils import build_thread_id
from app.core.security import get_current_user_id

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user_id: int = Depends(get_current_user_id)
):
    """
    聊天接口：支持订单查询和政策咨询

    - ORDER:  查询用户自己的订单
    - POLICY: 从知识库检索政策信息

    v4.1 更新：流式响应结束时发送置信度元数据
    """
    # 在函数内部导入，避免模块加载顺序问题
    from app.graph.workflow import app_graph

    if app_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is not fully initialized. Please try again in a moment."
        )

    async def event_generator():
        """SSE 流式响应生成器 - v4.1 支持置信度元数据"""
        thread_id = build_thread_id(current_user_id, request.thread_id)
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "question": request.question,
            "user_id": current_user_id,
            "thread_id": thread_id,
            "history": [],
            "context": [],
            "order_data": None,
            "answer": ""
        }

        # v4.1: 用于收集最终状态中的置信度信息
        final_state = {}

        try:
            async for event in app_graph.astream_events(
                initial_state, config, version="v2"
            ):
                kind = event["event"]

                # 处理 LLM 流式输出 - 只处理用户可见的 Agent 输出
                if kind == "on_chat_model_stream":
                    # 过滤内部调用（置信度评估、意图识别等）
                    metadata = event.get("metadata", {})
                    langgraph_node = metadata.get("langgraph_node", "")
                    tags = metadata.get("tags", [])

                    # 只转发标记为 user_visible 的输出
                    # 过滤掉 router 和内部置信度评估的调用
                    is_internal = (
                        langgraph_node == "router" or
                        "confidence_eval" in tags or
                        "internal" in tags
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

                    if output and isinstance(output, dict):
                        # 从 supervisor 节点获取 answer 发送给用户
                        # (对于 OrderAgent 等非 LLM 节点，answer 直接来自 state)
                        if langgraph_node == "supervisor" and "answer" in output:
                            answer = output["answer"]
                            if answer and answer not in getattr(event_generator, '_sent_answers', set()):
                                # 避免重复发送相同的 answer
                                if not hasattr(event_generator, '_sent_answers'):
                                    event_generator._sent_answers = set()
                                event_generator._sent_answers.add(answer)
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

        except Exception as e:
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

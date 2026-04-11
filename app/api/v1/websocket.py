# app/api/v1/websocket.py
"""
WebSocket 路由
"""

import logging

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from opentelemetry import trace

from app.core.logging import generate_correlation_id, set_correlation_id
from app.core.security import extract_bearer_token, get_current_user_id_ws, verify_admin_token
from app.core.utils import build_thread_id

router = APIRouter()

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@router.websocket("/ws/{thread_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    thread_id: str,
    token: str | None = Query(None),
):
    """
    用户 WebSocket 连接

    Query Params:
        token: JWT Token
    """
    with tracer.start_as_current_span("websocket_user") as span:
        span.set_attribute("websocket.type", "user")

        cid = websocket.headers.get("x-correlation-id") or generate_correlation_id()
        set_correlation_id(cid)

        auth_header = websocket.headers.get("authorization", "")
        bearer_token = extract_bearer_token(auth_header)
        if bearer_token:
            token = bearer_token
        if not token:
            await websocket.close(code=1008, reason="Missing authentication token")
            return
        try:
            # 验证 Token
            user_id = await get_current_user_id_ws(token)
            span.set_attribute("websocket.user_id", user_id)
        except HTTPException as exc:
            if exc.status_code in (401, 403):
                logger.warning(" [WS] 认证失败")
            else:
                logger.warning(" [WS] 连接错误: %s", exc)
            await websocket.close(code=1008, reason="Authentication failed")
            return

        # 限定 thread_id 作用域，防止跨用户订阅
        scoped_thread_id = build_thread_id(user_id, thread_id)
        span.set_attribute("websocket.thread_id", scoped_thread_id)

        # 建立连接
        try:
            await websocket.app.state.manager.connect_user(websocket, user_id, scoped_thread_id)
        except (WebSocketDisconnect, RuntimeError):
            logger.warning(" [WS] 连接错误")
            await websocket.close(code=1008, reason="Connection error")
            return

        try:
            while True:
                # 接收心跳或其他消息
                data = await websocket.receive_text()

                # 处理心跳
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        except RuntimeError as e:
            logger.warning(" [WS] 连接错误: %s", e)
        finally:
            await websocket.app.state.manager.disconnect_user(user_id, scoped_thread_id)


@router.websocket("/ws/admin/{admin_id}")
async def admin_websocket_endpoint(
    websocket: WebSocket,
    admin_id: int,
    token: str | None = Query(None),
):
    """
    管理员 WebSocket 连接

    Query Params:
        token: JWT Token (需验证管理员权限)
    """
    with tracer.start_as_current_span("websocket_admin") as span:
        span.set_attribute("websocket.type", "admin")
        span.set_attribute("websocket.admin_id", admin_id)

        cid = websocket.headers.get("x-correlation-id") or generate_correlation_id()
        set_correlation_id(cid)

        auth_header = websocket.headers.get("authorization", "")
        bearer_token = extract_bearer_token(auth_header)
        if bearer_token:
            token = bearer_token
        if not token:
            await websocket.close(code=1008, reason="Missing authentication token")
            return
        try:
            token_admin_id = verify_admin_token(token)
        except HTTPException:
            logger.warning(" [WS] 管理员认证失败")
            await websocket.close(code=1008, reason="Authentication failed")
            return

        if token_admin_id != admin_id:
            logger.warning(" [WS] 管理员 ID 不匹配")
            await websocket.close(code=1008, reason="Authentication failed")
            return

        # 建立连接
        try:
            await websocket.app.state.manager.connect_admin(websocket, admin_id)
        except (WebSocketDisconnect, RuntimeError):
            logger.warning(" [WS] 管理员连接错误")
            await websocket.close(code=1008, reason="Connection error")
            return

        try:
            while True:
                data = await websocket.receive_text()

                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        except RuntimeError as e:
            logger.warning(" [WS] 管理员连接错误: %s", e)
        finally:
            await websocket.app.state.manager.disconnect_admin(admin_id)

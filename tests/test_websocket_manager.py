from unittest.mock import AsyncMock

import pytest

from app.websocket.manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.mark.asyncio
async def test_connect_user_adds_connection(manager: ConnectionManager):
    ws = AsyncMock()
    await manager.connect_user(ws, user_id=1, thread_id="t1")
    assert manager.active_connections[1]["t1"] == ws
    assert ws in manager.thread_subscribers["t1"]


@pytest.mark.asyncio
async def test_connect_user_replaces_old_connection(manager: ConnectionManager):
    old_ws = AsyncMock()
    new_ws = AsyncMock()
    await manager.connect_user(old_ws, user_id=1, thread_id="t1")
    await manager.connect_user(new_ws, user_id=1, thread_id="t1")
    assert manager.active_connections[1]["t1"] == new_ws
    assert old_ws.close.await_count == 1
    assert old_ws not in manager.thread_subscribers["t1"]
    assert new_ws in manager.thread_subscribers["t1"]


@pytest.mark.asyncio
async def test_connect_admin_adds_connection(manager: ConnectionManager):
    ws = AsyncMock()
    await manager.connect_admin(ws, admin_id=1)
    assert manager.admin_connections[1] == ws


@pytest.mark.asyncio
async def test_disconnect_user_removes_connection(manager: ConnectionManager):
    ws = AsyncMock()
    await manager.connect_user(ws, user_id=1, thread_id="t1")
    await manager.disconnect_user(1, "t1")
    assert 1 not in manager.active_connections
    assert ws not in manager.thread_subscribers.get("t1", set())
    assert ws.close.await_count == 1


@pytest.mark.asyncio
async def test_disconnect_admin_removes_connection(manager: ConnectionManager):
    ws = AsyncMock()
    await manager.connect_admin(ws, admin_id=1)
    await manager.disconnect_admin(1)
    assert 1 not in manager.admin_connections
    assert ws.close.await_count == 1


@pytest.mark.asyncio
async def test_send_to_user_delivers_message(manager: ConnectionManager):
    ws = AsyncMock()
    await manager.connect_user(ws, user_id=1, thread_id="t1")
    await manager.send_to_user(1, "t1", {"msg": "hello"})
    ws.send_json.assert_awaited_once_with({"msg": "hello"})


@pytest.mark.asyncio
async def test_send_to_user_handles_disconnected_client(manager: ConnectionManager):
    ws = AsyncMock()
    ws.send_json.side_effect = RuntimeError("disconnected")
    await manager.connect_user(ws, user_id=1, thread_id="t1")
    await manager.send_to_user(1, "t1", {"msg": "hello"})
    assert 1 not in manager.active_connections


@pytest.mark.asyncio
async def test_send_to_thread_broadcasts_to_subscribers(manager: ConnectionManager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect_user(ws1, user_id=1, thread_id="t1")
    await manager.connect_user(ws2, user_id=2, thread_id="t1")
    await manager.send_to_thread("t1", {"type": "update"})
    ws1.send_json.assert_awaited_once_with({"type": "update"})
    ws2.send_json.assert_awaited_once_with({"type": "update"})


@pytest.mark.asyncio
async def test_broadcast_to_admins_sends_to_all_admins(manager: ConnectionManager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect_admin(ws1, admin_id=1)
    await manager.connect_admin(ws2, admin_id=2)
    await manager.broadcast_to_admins({"alert": "test"})
    ws1.send_json.assert_awaited_once_with({"alert": "test"})
    ws2.send_json.assert_awaited_once_with({"alert": "test"})


@pytest.mark.asyncio
async def test_notify_status_change_sends_to_thread(manager: ConnectionManager):
    ws = AsyncMock()
    await manager.connect_user(ws, user_id=1, thread_id="t1")
    await manager.notify_status_change("t1", "APPROVED", {"refund_id": 123})
    ws.send_json.assert_awaited_once()
    call_args = ws.send_json.await_args.args[0]
    assert call_args["type"] == "status_change"
    assert call_args["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_notify_status_change_waiting_admin_alerts_admins(manager: ConnectionManager):
    user_ws = AsyncMock()
    admin_ws = AsyncMock()
    await manager.connect_user(user_ws, user_id=1, thread_id="t1")
    await manager.connect_admin(admin_ws, admin_id=1)
    await manager.notify_status_change("t1", "WAITING_ADMIN", {"task": "review"})
    user_ws.send_json.assert_awaited_once()
    admin_ws.send_json.assert_awaited_once()
    admin_call = admin_ws.send_json.await_args.args[0]
    assert admin_call["type"] == "new_audit_task"

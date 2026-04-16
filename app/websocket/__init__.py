# app/websocket/__init__.py
"""
WebSocket 实时通信模块
"""

from app.websocket.manager import ConnectionManager, get_manager, manager

__all__ = ["ConnectionManager", "get_manager", "manager"]

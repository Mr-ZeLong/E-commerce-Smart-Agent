from typing import Any

from pydantic import BaseModel


class StatusResponse(BaseModel):
    """状态响应"""
    thread_id: str
    status: str  # "PROCESSING", "WAITING_ADMIN", "APPROVED", "REJECTED", "COMPLETED", "ERROR"
    message: str | None = None
    data: dict[str, Any] | None = None
    timestamp: str

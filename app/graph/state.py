# app/graph/state.py
# v4.1 向后兼容层
# 此文件保留以确保现有代码不中断，将在 v5.0 移除

import warnings

from app.models.state import (
    AgentState,
    RetrievalResult,
    get_audit_level_from_old,
    get_audit_required,
    normalize_state,
)

__all__ = [
    "AgentState",
    "RetrievalResult",
    "get_audit_level_from_old",
    "get_audit_required",
    "normalize_state",
]

# 向后兼容警告
warnings.warn(
    "app.graph.state is deprecated, use app.models.state instead",
    DeprecationWarning,
    stacklevel=2,
)

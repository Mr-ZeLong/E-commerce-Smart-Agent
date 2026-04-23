# app/tasks/__init__.py
"""
Celery 异步任务模块
"""

from app.tasks import alert_tasks, autoheal_tasks, knowledge_tasks, memory_tasks
from app.tasks.evaluation_tasks import run_few_shot_evaluation
from app.tasks.notifications import (
    check_quality_alerts,
    send_complaint_alert,
    send_status_update,
)
from app.tasks.observability_tasks import log_chat_observability
from app.tasks.prompt_effect_tasks import generate_monthly_report
from app.tasks.refund_tasks import (
    notify_admin_audit,
    process_refund_payment,
    send_refund_sms,
)

__all__ = [
    "alert_tasks",
    "autoheal_tasks",
    "check_quality_alerts",
    "generate_monthly_report",
    "knowledge_tasks",
    "log_chat_observability",
    "memory_tasks",
    "notify_admin_audit",
    "process_refund_payment",
    "run_few_shot_evaluation",
    "send_complaint_alert",
    "send_refund_sms",
    "send_status_update",
]

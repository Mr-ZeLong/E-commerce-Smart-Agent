# app/celery_app.py
"""Celery 异步任务系统
处理短信发送、退款网关调用等耗时操作
"""

from celery import Celery

from app.core.config import settings
from app.observability.otel_setup import setup_celery_tracing
from app.tasks.tracing_setup import setup_celery_langsmith_tracing

# 创建 Celery 实例
celery_app = Celery(
    "ecommerce_agent",
    broker=settings.CELERY_BROKER_URL.get_secret_value(),
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5分钟超时
    task_soft_time_limit=240,  # 4分钟软超时
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    beat_schedule={
        "prune-vector-memory-daily": {
            "task": "memory.prune_vector_memory",
            "schedule": 86400.0,
        },
        "check-quality-alerts": {
            "task": "notifications.check_quality_alerts",
            "schedule": 300.0,
        },
        "generate-prompt-effect-reports-monthly": {
            "task": "prompt_effect.generate_monthly_report",
            "schedule": 2592000.0,
        },
        "cleanup-old-checkpoints-daily": {
            "task": "checkpoint.cleanup_old_checkpoints",
            "schedule": 86400.0,
        },
        "check-celery-workers": {
            "task": "autoheal.check_celery_workers",
            "schedule": 300.0,
        },
        "clear-redis-cache": {
            "task": "autoheal.clear_redis_cache",
            "schedule": 600.0,
        },
        "restart-stuck-workers": {
            "task": "autoheal.restart_stuck_workers",
            "schedule": 300.0,
        },
        "clear-expired-redis-keys": {
            "task": "autoheal.clear_expired_redis_keys",
            "schedule": 600.0,
        },
        "check-db-pool-health": {
            "task": "autoheal.check_db_pool_health",
            "schedule": 300.0,
        },
        "evaluate-alert-rules": {
            "task": "alerting.evaluate_rules",
            "schedule": 60.0,
        },
        "check-service-health": {
            "task": "alerting.check_service_health",
            "schedule": 30.0,
        },
        "run-shadow-tests": {
            "task": "shadow.run_shadow_test",
            "schedule": 60.0,
        },
        "run-adversarial-suite": {
            "task": "evaluation.run_adversarial_suite",
            "schedule": 86400.0,
        },
    },
)

# Configure LangSmith tracing for Celery workers BEFORE autodiscover (env vars must be set before potential langchain imports)
setup_celery_langsmith_tracing()

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])

# Instrument Celery with OpenTelemetry tracing
setup_celery_tracing()

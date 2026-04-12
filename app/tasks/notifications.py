import asyncio
import logging
from datetime import datetime, timedelta

from sqlmodel import func, select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.core.email import send_email
from app.models.complaint import ComplaintTicket
from app.models.evaluation import MessageFeedback

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="notifications.send_complaint_alert", max_retries=2)
def send_complaint_alert(self, ticket_id: int, recipient_email: str) -> dict:
    subject = f"投诉工单 #{ticket_id} 高优先级告警"
    body = f"工单 #{ticket_id} 被标记为高优先级，请及时处理。"
    result = asyncio.run(send_email([recipient_email], subject, body))
    return {"ticket_id": ticket_id, "recipient": recipient_email, **result}


@celery_app.task(bind=True, name="notifications.send_status_update", max_retries=2)
def send_status_update(self, ticket_id: int, recipient_email: str) -> dict:
    subject = f"投诉工单 #{ticket_id} 状态更新"
    body = f"工单 #{ticket_id} 状态已更新，请登录后台查看详情。"
    result = asyncio.run(send_email([recipient_email], subject, body))
    return {"ticket_id": ticket_id, "recipient": recipient_email, **result}


@celery_app.task(bind=True, name="notifications.check_quality_alerts")
def check_quality_alerts(self) -> dict:
    from app.core.config import settings

    window_hours = getattr(settings, "ALERT_COMPLAINT_WINDOW_HOURS", 24)
    csat_threshold = getattr(settings, "ALERT_CSAT_THRESHOLD", 0.7)
    complaint_max = getattr(settings, "ALERT_COMPLAINT_MAX", 10)
    admin_emails = getattr(settings, "ALERT_ADMIN_EMAILS", [])

    since = datetime.utcnow() - timedelta(hours=window_hours)

    async def _check() -> dict:
        async with async_session_maker() as session:
            up_result = await session.exec(
                select(func.count()).where(
                    MessageFeedback.created_at >= since,
                    MessageFeedback.score == 1,
                )
            )
            thumbs_up = up_result.one()

            down_result = await session.exec(
                select(func.count()).where(
                    MessageFeedback.created_at >= since,
                    MessageFeedback.score == -1,
                )
            )
            thumbs_down = down_result.one()

            complaint_result = await session.exec(
                select(func.count()).where(
                    ComplaintTicket.created_at >= since,
                )
            )
            complaint_count = complaint_result.one()

            total = thumbs_up + thumbs_down
            csat = thumbs_up / total if total > 0 else 1.0

            alert_triggered = False
            reasons = []
            if csat < csat_threshold:
                alert_triggered = True
                reasons.append(f"CSAT {csat:.2f} < threshold {csat_threshold}")
            if complaint_count > complaint_max:
                alert_triggered = True
                reasons.append(f"complaints {complaint_count} > max {complaint_max}")

            if alert_triggered and admin_emails:
                subject = "智能客服质量告警"
                body = (
                    f"过去 {window_hours} 小时指标异常:\n"
                    f"- CSAT: {csat:.2f} (点赞 {thumbs_up}, 点踩 {thumbs_down})\n"
                    f"- 投诉工单数: {complaint_count}\n"
                    f"原因: {', '.join(reasons)}"
                )
                for email in admin_emails:
                    await send_email([email], subject, body)

            # TODO: broadcast WebSocket alert to admin dashboards when manager is available
            return {
                "alert_triggered": alert_triggered,
                "csat": csat,
                "complaint_count": complaint_count,
                "reasons": reasons,
            }

    return asyncio.run(_check())

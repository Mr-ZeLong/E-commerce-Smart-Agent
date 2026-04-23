import logging
from datetime import UTC, datetime, timedelta

from sqlmodel import func, select

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import sync_session_maker
from app.models.complaint import ComplaintTicket
from app.models.evaluation import MessageFeedback

logger = logging.getLogger(__name__)


def _sync_send_email(to_emails: list[str], subject: str, body: str) -> dict:
    """同步发送邮件（Celery任务专用）"""
    import smtplib
    from email.mime.text import MIMEText

    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP 未配置，跳过邮件发送")
        return {"sent": False, "reason": "smtp_not_configured"}

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    msg["To"] = ", ".join(to_emails)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_PORT == 587:
                server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD.get_secret_value())
            server.sendmail(msg["From"], to_emails, msg.as_string())
        logger.info("邮件已发送至 %s", to_emails)
        return {"sent": True, "recipients": to_emails}
    except (smtplib.SMTPException, OSError, ConnectionError):
        logger.exception("邮件发送失败")
        return {"sent": False, "reason": "smtp_error"}


@celery_app.task(bind=True, name="notifications.send_complaint_alert", max_retries=2)
def send_complaint_alert(_self, ticket_id: int, recipient_email: str) -> dict:
    subject = f"投诉工单 #{ticket_id} 高优先级告警"
    body = f"工单 #{ticket_id} 被标记为高优先级，请及时处理。"
    result = _sync_send_email([recipient_email], subject, body)
    return {"ticket_id": ticket_id, "recipient": recipient_email, **result}


@celery_app.task(bind=True, name="notifications.send_status_update", max_retries=2)
def send_status_update(_self, ticket_id: int, recipient_email: str) -> dict:
    subject = f"投诉工单 #{ticket_id} 状态更新"
    body = f"工单 #{ticket_id} 状态已更新，请登录后台查看详情。"
    result = _sync_send_email([recipient_email], subject, body)
    return {"ticket_id": ticket_id, "recipient": recipient_email, **result}


@celery_app.task(bind=True, name="notifications.check_quality_alerts")
def check_quality_alerts(_self) -> dict:
    window_hours = getattr(settings, "ALERT_COMPLAINT_WINDOW_HOURS", 24)
    csat_threshold = getattr(settings, "ALERT_CSAT_THRESHOLD", 0.7)
    complaint_max = getattr(settings, "ALERT_COMPLAINT_MAX", 10)
    admin_emails = getattr(settings, "ALERT_ADMIN_EMAILS", [])

    since = datetime.now(UTC) - timedelta(hours=window_hours)

    with sync_session_maker() as session:
        result = session.exec(
            select(func.count()).where(
                MessageFeedback.created_at >= since,
                MessageFeedback.score == 1,
            )
        )
        thumbs_up = result.one()

        result = session.exec(
            select(func.count()).where(
                MessageFeedback.created_at >= since,
                MessageFeedback.score == -1,
            )
        )
        thumbs_down = result.one()

        result = session.exec(
            select(func.count()).where(
                ComplaintTicket.created_at >= since,
            )
        )
        complaint_count = result.one()

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

        if alert_triggered:
            body = (
                f"过去 {window_hours} 小时指标异常:\n"
                f"- CSAT: {csat:.2f} (点赞 {thumbs_up}, 点踩 {thumbs_down})\n"
                f"- 投诉工单数: {complaint_count}\n"
                f"原因: {', '.join(reasons)}"
            )
            if admin_emails:
                subject = "智能客服质量告警"
                for email in admin_emails:
                    _sync_send_email([email], subject, body)

        return {
            "alert_triggered": alert_triggered,
            "csat": csat,
            "complaint_count": complaint_count,
            "reasons": reasons,
        }

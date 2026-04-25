"""通用邮件发送工具"""

import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to_emails: list[str], subject: str, body: str) -> dict:
    """发送邮件（同步底层，异步包装）"""
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
    except (smtplib.SMTPException, OSError, ConnectionError, Exception):
        logger.exception("邮件发送失败")
        return {"sent": False, "reason": "smtp_error"}

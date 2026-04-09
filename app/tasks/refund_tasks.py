# app/tasks/refund_tasks.py
"""
退款相关异步任务
"""
import asyncio
import concurrent.futures
from datetime import UTC, datetime
from typing import Any

from celery import Task
from sqlmodel import select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.models.audit import AuditLog
from app.models.message import MessageCard, MessageStatus, MessageType
from app.models.refund import RefundApplication, RefundStatus


class DatabaseTask(Task):
    """支持异步数据库操作的 Celery Task 基类"""
    _session = None

    def run_async(self, coro):
        """在 Celery worker 中安全运行异步函数"""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # 如果当前线程已有运行中的事件循环，创建新线程来运行
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
        except RuntimeError:
            pass
        # 没有运行中的事件循环，直接使用 asyncio.run
        return asyncio.run(coro)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="refund.send_sms",
    max_retries=3,
    default_retry_delay=60
)
def send_refund_sms(self, refund_id: int, phone:  str, message: str) -> dict[str, Any]:
    """
    发送退款通知短信

    Args:
        refund_id:  退款申请ID
        phone: 手机号
        message: 短信内容
    """
    try:
        # TODO: 接入真实短信网关 (阿里云、腾讯云等)
        print(f"📱 [SMS] 发送短信到 {phone}: {message}")

        # 模拟短信发送
        import time
        time.sleep(2)

        # 记录发送成功
        return {
            "status": "success",
            "refund_id": refund_id,
            "phone": phone,
            "sent_at": datetime.now(UTC).isoformat(),
        }

    except Exception as exc:
        # 重试机制
        print(f"  [SMS] 发送失败: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="refund.process_payment",
    max_retries=3,
    default_retry_delay=120
)
def process_refund_payment(self, refund_id: int, amount: float, payment_method: str) -> dict[str, Any]:
    """
    调用支付网关执行退款

    Args:
        refund_id:  退款申请ID
        amount: 退款金额
        payment_method: 支付方式
    """
    async def _process():
        try:
            async with async_session_maker() as session:
                # 查询退款申请
                result = await session.execute(  # ty:ignore[deprecated]
                    select(RefundApplication).where(RefundApplication.id == refund_id)
                )
                refund = result.scalar_one_or_none()

                if not refund:
                    raise ValueError(f"Refund application {refund_id} not found")

                # TODO: 接入真实支付网关 (支付宝、微信支付等)
                print(f"💰 [Payment] 退款 ¥{amount} 到 {payment_method}")

                # 模拟支付网关调用
                import time
                time.sleep(3)

                # 更新退款状态
                refund.status = RefundStatus.COMPLETED
                refund.updated_at = datetime.now(UTC).replace(tzinfo=None)
                session.add(refund)
                await session.commit()

                return {
                    "status": "success",
                    "refund_id": refund_id,
                    "amount": amount,
                    "transaction_id": f"TXN{refund_id}{int(time.time())}",
                    "completed_at": datetime.now(UTC).isoformat(),
                }

        except Exception as exc:
            print(f"  [Payment] 退款失败: {exc}")
            raise exc

    try:
        return self.run_async(_process())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="refund.notify_admin",
    max_retries=2
)
def notify_admin_audit(self, audit_log_id: int) -> dict[str, Any]:
    """
    通知管理员有新的审核任务

    Args:
        audit_log_id: 审计日志ID
    """
    async def _notify():
        async with async_session_maker() as session:
            # 查询审计日志
            result = await session.execute(  # ty:ignore[deprecated]
                select(AuditLog).where(AuditLog.id == audit_log_id)
            )
            audit_log = result.scalar_one_or_none()

            if not audit_log:
                raise ValueError(f"Audit log {audit_log_id} not found")

            # TODO: 接入真实通知系统 (邮件、企业微信、钉钉等)
            print("  [Notify] 通知管理员审核任务:")
            print(f"  - 风险等级: {audit_log.risk_level}")
            print(f"  - 触发原因: {audit_log.trigger_reason}")
            print(f"  - 用户ID: {audit_log.user_id}")

            # 创建系统消息通知 B 端
            message = MessageCard(
                thread_id=audit_log.thread_id,
                message_type=MessageType.SYSTEM,
                status=MessageStatus.SENT,
                content={
                    "type": "admin_notification",
                    "audit_log_id": audit_log_id,
                    "risk_level": audit_log.risk_level,
                    "message": f"新的{audit_log.risk_level}风险审核任务",
                },
                sender_type="system",
                receiver_id=None,  # 广播给所有管理员
            )
            session.add(message)
            await session.commit()

            return {
                "status": "success",
                "audit_log_id": audit_log_id,
                "notified_at": datetime.now(UTC).isoformat(),
            }

    try:
        return self.run_async(_notify())
    except Exception as exc:
        print(f"  [Notify] 通知失败:  {exc}")
        raise self.retry(exc=exc)

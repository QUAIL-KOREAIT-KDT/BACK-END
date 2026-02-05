# BACK-END/app/domains/notification/repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, delete
from sqlalchemy.sql import func
from app.domains.notification.models import Notification
from app.domains.user.models import User
from typing import List, Optional
from datetime import datetime, timedelta


class NotificationRepository:

    async def create(self, db: AsyncSession, notification: Notification) -> Notification:
        """알림 생성"""
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def get_by_user(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Notification]:
        """사용자의 알림 목록 조회 (최신순)"""
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(desc(Notification.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_unread_count(self, db: AsyncSession, user_id: int) -> int:
        """읽지 않은 알림 개수 조회"""
        result = await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        )
        return result.scalar() or 0

    async def mark_as_read(self, db: AsyncSession, notification_id: int, user_id: int) -> bool:
        """알림 읽음 처리"""
        result = await db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
            .values(is_read=True, read_at=func.now())
        )
        await db.commit()
        return result.rowcount > 0

    async def mark_all_as_read(self, db: AsyncSession, user_id: int) -> int:
        """모든 알림 읽음 처리"""
        result = await db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
            .values(is_read=True, read_at=func.now())
        )
        await db.commit()
        return result.rowcount

    async def delete_notification(self, db: AsyncSession, notification_id: int, user_id: int) -> bool:
        """알림 삭제"""
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
        notification = result.scalar_one_or_none()
        if notification:
            await db.delete(notification)
            await db.commit()
            return True
        return False

    async def delete_all_notifications(self, db: AsyncSession, user_id: int) -> int:
        """사용자의 모든 알림 삭제"""
        result = await db.execute(
            delete(Notification).where(Notification.user_id == user_id)
        )
        await db.commit()
        return result.rowcount

    async def delete_old_notifications(self, db: AsyncSession, days: int = 30) -> int:
        """오래된 알림 삭제 (30일 이전)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await db.execute(
            delete(Notification).where(Notification.created_at < cutoff_date)
        )
        await db.commit()
        return result.rowcount

    async def update_fcm_token(self, db: AsyncSession, user_id: int, fcm_token: str):
        """사용자 FCM 토큰 업데이트"""
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(fcm_token=fcm_token)
        )
        await db.commit()

    async def get_user_fcm_info(self, db: AsyncSession, user_id: int) -> Optional[dict]:
        """사용자 FCM 정보 조회 (토큰 + 알림 설정)"""
        result = await db.execute(
            select(User.fcm_token, User.notification_settings)
            .where(User.id == user_id)
        )
        row = result.first()
        if row:
            return {
                "fcm_token": row.fcm_token,
                "notification_enabled": row.notification_settings
            }
        return None

    async def get_notification_enabled_users(self, db: AsyncSession) -> List[User]:
        """알림 수신 활성화된 사용자 목록 조회"""
        result = await db.execute(
            select(User)
            .where(
                User.notification_settings == True,
                User.fcm_token.isnot(None)
            )
        )
        return result.scalars().all()


# 싱글톤 인스턴스
notification_repository = NotificationRepository()

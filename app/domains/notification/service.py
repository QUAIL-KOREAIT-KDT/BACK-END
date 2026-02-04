# BACK-END/app/domains/notification/service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.notification.repository import notification_repository
from app.domains.notification.models import Notification
from app.utils.fcm_service import fcm_service
import logging
import json

logger = logging.getLogger(__name__)


class NotificationService:

    async def send_notification(
        self,
        db: AsyncSession,
        user_id: int,
        type: str,
        title: str,
        message: str,
        data: dict = None
    ) -> bool:
        """
        알림 생성 + FCM 푸시 전송

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            type: 알림 타입 (daily, notice)
            title: 알림 제목
            message: 알림 내용
            data: 추가 데이터

        Returns:
            bool: 전송 성공 여부
        """
        # 1. 사용자 FCM 정보 조회
        fcm_info = await notification_repository.get_user_fcm_info(db, user_id)

        # 2. DB에 알림 저장
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=json.dumps(data, ensure_ascii=False) if data else None,
            is_sent=False
        )
        await notification_repository.create(db, notification)

        # 3. FCM 전송 (토큰이 있고 알림 수신 활성화된 경우)
        if fcm_info and fcm_info.get("fcm_token") and fcm_info.get("notification_enabled"):
            success = await fcm_service.send_push(
                token=fcm_info["fcm_token"],
                title=title,
                body=message,
                data={
                    "notification_id": str(notification.id),
                    "type": type,
                    **(data or {})
                }
            )

            # 전송 성공 시 is_sent 업데이트
            if success:
                notification.is_sent = True
                await db.commit()

            return success
        else:
            logger.info(f"User {user_id}: FCM 토큰 없음 또는 알림 비활성화")
            return False

    async def send_daily_notification(
        self,
        db: AsyncSession,
        user_id: int,
        risk_percentage: int,
        ventilation_time: str
    ):
        """
        매일 오전 8시 정기 알림
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            risk_percentage: 곰팡이 위험도 (%)
            ventilation_time: 추천 환기 시간
        """
        # 위험도에 따른 이모지 및 메시지 설정
        if risk_percentage >= 80:
            emoji = "🚨"
            level_msg = "위험"
        elif risk_percentage >= 60:
            emoji = "⚠️"
            level_msg = "주의"
        elif risk_percentage >= 30:
            emoji = "💧"
            level_msg = "보통"
        else:
            emoji = "✨"
            level_msg = "좋음"

        title = f"{emoji} 오늘의 곰팡이 정보"
        message = f"오늘 곰팡이 위험도는 {risk_percentage}% ({level_msg})입니다.\n추천 환기 시간: {ventilation_time}"

        await self.send_notification(
            db,
            user_id,
            "daily",
            title,
            message,
            data={
                "risk_percentage": risk_percentage,
                "ventilation_time": ventilation_time
            }
        )

    async def send_bulk_daily_notifications(
        self,
        db: AsyncSession,
        notifications_data: list[dict]
    ) -> dict:
        """
        대량 정기 알림 전송
        
        Args:
            notifications_data: [{"user_id": int, "fcm_token": str, "risk_percentage": int, "ventilation_time": str}, ...]
        
        Returns:
            dict: {"success_count": int, "failure_count": int}
        """
        success_count = 0
        failure_count = 0

        for data in notifications_data:
            try:
                await self.send_daily_notification(
                    db,
                    data["user_id"],
                    data["risk_percentage"],
                    data["ventilation_time"]
                )
                success_count += 1
            except Exception as e:
                logger.error(f"User {data['user_id']} 알림 전송 실패: {str(e)}")
                failure_count += 1

        return {
            "success_count": success_count,
            "failure_count": failure_count
        }


# 싱글톤 인스턴스
notification_service = NotificationService()

# BACK-END/app/domains/notification/schemas.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class NotificationCreate(BaseModel):
    """알림 생성 요청"""
    user_id: int
    type: str = "daily"  # daily, notice
    title: str
    message: str
    data: Optional[dict] = None


class NotificationResponse(BaseModel):
    """알림 응답"""
    id: int
    type: str
    title: str
    message: str
    data: Optional[Any] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FCMTokenUpdate(BaseModel):
    """FCM 토큰 등록/수정"""
    fcm_token: str


class NotificationSettingsUpdate(BaseModel):
    """알림 설정 변경"""
    notification_enabled: bool

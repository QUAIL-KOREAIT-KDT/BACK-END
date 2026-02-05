# BACK-END/app/domains/notification/router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.notification.schemas import (
    NotificationResponse,
    FCMTokenUpdate,
    NotificationSettingsUpdate
)
from app.domains.notification.repository import notification_repository
from app.domains.notification.service import notification_service
from app.domains.user.repository import UserRepository
import json

router = APIRouter()
user_repo = UserRepository()


@router.post("/register-token")
async def register_fcm_token(
    body: FCMTokenUpdate,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """
    FCM 토큰 등록/갱신
    
    - 앱 시작 시 또는 토큰 갱신 시 호출
    - 기존 토큰이 있으면 덮어씀
    """
    await notification_repository.update_fcm_token(db, user_id, body.fcm_token)
    return {
        "status": "success",
        "message": "FCM 토큰이 등록되었습니다."
    }


@router.get("/", response_model=list[NotificationResponse])
async def get_notifications(
    limit: int = 50,
    offset: int = 0,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """
    알림 목록 조회
    
    - 최신순으로 정렬
    - 기본 50개, offset으로 페이징
    """
    notifications = await notification_repository.get_by_user(db, user_id, limit, offset)

    # data 필드 JSON 파싱
    result = []
    for noti in notifications:
        noti_dict = {
            "id": noti.id,
            "type": noti.type,
            "title": noti.title,
            "message": noti.message,
            "data": json.loads(noti.data) if noti.data else None,
            "is_read": noti.is_read,
            "created_at": noti.created_at
        }
        result.append(noti_dict)

    return result


@router.get("/unread-count")
async def get_unread_count(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """읽지 않은 알림 개수 조회"""
    count = await notification_repository.get_unread_count(db, user_id)
    return {"unread_count": count}


@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """알림 읽음 처리"""
    success = await notification_repository.mark_as_read(db, notification_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림을 찾을 수 없습니다."
        )
    return {"status": "success"}


@router.patch("/read-all")
async def mark_all_notifications_as_read(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """모든 알림 읽음 처리"""
    count = await notification_repository.mark_all_as_read(db, user_id)
    return {"status": "success", "marked_count": count}


@router.delete("/delete-all")
async def delete_all_notifications(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """모든 알림 삭제"""
    count = await notification_repository.delete_all_notifications(db, user_id)
    return {"status": "success", "deleted_count": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """알림 삭제"""
    success = await notification_repository.delete_notification(db, notification_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림을 찾을 수 없습니다."
        )
    return {"status": "success"}


@router.put("/settings")
async def update_notification_settings(
    body: NotificationSettingsUpdate,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """
    알림 수신 설정 변경 (ON/OFF)
    """
    user = await user_repo.update_user(
        db,
        user_id,
        notification_settings=body.notification_enabled
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    return {
        "status": "success",
        "notification_enabled": body.notification_enabled
    }


@router.get("/settings")
async def get_notification_settings(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """알림 수신 설정 조회"""
    user = await user_repo.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    return {
        "notification_enabled": user.notification_settings if user.notification_settings is not None else True
    }


# ========== 테스트용 API ==========
@router.post("/test-send")
async def test_send_notification(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """
    테스트 알림 전송 (개발용)
    
    - 자신에게 테스트 알림을 보냄
    """
    success = await notification_service.send_notification(
        db,
        user_id,
        "notice",
        "🧪 테스트 알림",
        "알림 기능이 정상 작동합니다!"
    )
    return {
        "status": "success" if success else "fail",
        "message": "알림이 전송되었습니다." if success else "FCM 토큰이 없거나 알림이 비활성화되었습니다."
    }

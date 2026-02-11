# BACK-END/app/domains/notification/models.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime
import pytz

def get_now_kst():
    return datetime.now(pytz.timezone('Asia/Seoul'))

class Notification(Base):
    """
    사용자 알림 이력 테이블
    - 매일 오전 8시 정기 알림 저장
    - 공지사항 등 운영 알림 저장
    """
    __tablename__ = "notifications"

    # 알림 고유 ID
    id = Column(Integer, primary_key=True, index=True)

    # 사용자 ID (Foreign Key)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 알림 타입 (daily: 매일 8시 알림, notice: 공지사항)
    type = Column(String(20), nullable=False, default="daily")

    # 제목
    title = Column(String(100), nullable=False)

    # 내용
    message = Column(Text, nullable=False)

    # 추가 데이터 (JSON 문자열: risk_percentage, ventilation_time 등)
    data = Column(Text, nullable=True)

    # 읽음 여부
    is_read = Column(Boolean, default=False)

    # 발송 성공 여부
    is_sent = Column(Boolean, default=False)

    # 생성일
    created_at = Column(DateTime(timezone=True), default=get_now_kst)

    # 읽은 시간
    read_at = Column(DateTime(timezone=True), nullable=True)

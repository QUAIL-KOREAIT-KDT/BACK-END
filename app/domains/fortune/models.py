# BACK-END/app/domains/fortune/models.py

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from app.core.database import Base
from datetime import datetime
import pytz


def get_now_kst():
    return datetime.now(pytz.timezone('Asia/Seoul'))


class FortuneHistory(Base):
    """
    사용자별 오늘의 팡이 운세 조회 이력
    - 하루 1회 제한 및 결과 재조회에 활용
    """
    __tablename__ = "fortune_histories"

    id = Column(Integer, primary_key=True, index=True)

    # 사용자 ID (Foreign Key)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 운세 점수 (0~100)
    score = Column(Integer, nullable=False)

    # 상태 요약 (예: "뽀송함", "축축함")
    status = Column(String(50), nullable=False)

    # 팡이의 한 줄 메시지
    message = Column(Text, nullable=False)

    # 기준 날짜 (YYYY-MM-DD, 한국 시간 기준)
    fortune_date = Column(String(10), nullable=False)

    # 생성일시
    created_at = Column(DateTime(timezone=True), default=get_now_kst)

    # user_id + fortune_date 조합은 유일 (하루 1회 보장)
    __table_args__ = (
        UniqueConstraint('user_id', 'fortune_date', name='uix_fortune_user_date'),
    )

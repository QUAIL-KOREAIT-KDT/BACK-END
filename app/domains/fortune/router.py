# BACK-END/app/domains/fortune/router.py

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import pytz

from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.fortune.service import fortune_service
from app.domains.fortune.models import FortuneHistory

router = APIRouter()


def _get_today_kst() -> str:
    """한국 시간 기준 오늘 날짜 문자열 반환 (YYYY-MM-DD)"""
    return datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')


@router.get("/today")
async def get_fortune(
    q: str = Query(None, description="팡이에게 물어볼 고민"),
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """
    오늘의 팡이 운세 조회 (하루 1회 제한)
    - 오늘 이미 조회한 경우: 저장된 결과 반환
    - 처음 조회하는 경우: Gemini API 호출 후 저장
    """
    today = _get_today_kst()

    # 오늘 이미 조회했는지 확인
    result = await db.execute(
        select(FortuneHistory).where(
            FortuneHistory.user_id == user_id,
            FortuneHistory.fortune_date == today,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # 저장된 결과 반환
        return {
            "score": existing.score,
            "status": existing.status,
            "message": existing.message,
            "already_viewed": True,
        }

    # 새 운세 생성
    fortune = await fortune_service.generate_pangi_fortune(user_question=q)

    # DB에 저장
    new_record = FortuneHistory(
        user_id=user_id,
        score=fortune.get("score", 50),
        status=fortune.get("status", ""),
        message=fortune.get("message", ""),
        fortune_date=today,
    )
    db.add(new_record)
    await db.commit()

    return {
        "score": fortune.get("score"),
        "status": fortune.get("status"),
        "message": fortune.get("message"),
        "already_viewed": False,
    }

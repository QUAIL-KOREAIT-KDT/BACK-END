# BACK-END/app/domains/home/router.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.home.service import home_service
from app.domains.home.schemas import HomeResponse

router = APIRouter()

@router.get("/info", response_model=HomeResponse)
async def get_home_page_info(
    user_id: int = Depends(verify_token), # 토큰에서 user_id 추출
    db: AsyncSession = Depends(get_db)
):
    """
    [홈 화면 정보 조회]
    1. 오늘 현재 시간 이후의 날씨 예보 리스트
    2. 오늘/내일 중 환기 가능한 시간대 (2시간 이상 연속 조건)
    """
    return await home_service.get_home_view(user_id, db)
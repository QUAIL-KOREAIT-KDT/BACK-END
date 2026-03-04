# BACK-END/app/domains/game/router.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.game.schemas import ScoreSubmit
from app.domains.game.service import GameService

router = APIRouter()
service = GameService()


@router.post("/score")
async def submit_score(
    data: ScoreSubmit,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """게임 종료 시 점수 제출"""
    return await service.submit_score(db, user_id, data.score)


@router.get("/ranking")
async def get_ranking(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """상위 10명 랭킹 + 내 순위 조회"""
    return await service.get_rankings(db, user_id)


@router.get("/my-best")
async def get_my_best(
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
):
    """내 최고 점수 및 플레이 횟수 조회"""
    return await service.get_personal_best(db, user_id)

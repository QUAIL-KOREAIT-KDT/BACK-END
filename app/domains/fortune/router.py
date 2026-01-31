# BACK-END/app/domains/fortune/router.py

from fastapi import APIRouter, Query
from app.domains.fortune.service import fortune_service

router = APIRouter()

@router.get("/today")
async def get_fortune(q: str = Query(None, description="팡이에게 물어볼 고민")):
    """
    사용자 질문이 있으면 가족 같은 조언을, 없으면 오늘의 운세를 반환합니다.
    """
    result = await fortune_service.generate_pangi_fortune(user_question=q)
    return result
# BACK-END/app/domains/fortune/router.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/today")
async def get_fortune():
    """[Source 5] 오늘의 팡이 운세 (핸드폰 흔들기 후 호출)"""
    return {
        "score": 85,
        "status": "뽀송함", # [Source 5]
        "message": "오늘은 곰팡이 걱정 없는 날!"
    }
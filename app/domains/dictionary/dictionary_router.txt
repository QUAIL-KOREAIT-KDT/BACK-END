# BACK-END/app/domains/dictionary/router.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/list")
async def get_mold_dictionary():
    """[Source 4] 곰팡이 도감 목록 조회"""
    # DB에서 [Source 12] 데이터 조회
    pass
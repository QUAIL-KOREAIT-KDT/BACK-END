# BACK-END/app/domains/dictionary/router.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List


from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.dictionary.schemas import DictionaryResponse
from app.domains.dictionary.service import DictionaryService

router = APIRouter()
service = DictionaryService()

@router.get("/list", response_model=List[DictionaryResponse])
async def get_mold_dictionary(
    user_id:int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
    ):
    """
    [Source 4] 곰팡이 도감 목록 조회
    - 로그인 시 미리 호출하여 앱 내부에 저장하는 용도입니다.
    """
    return await service.get_dictionary_list(db)
# BACK-END/app/domains/search/router.py

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.domains.search.service import SearchService

router = APIRouter()
service = SearchService()


@router.get("/query")
async def search_mold_info(q: str):
    """Released-app compatible mold query endpoint."""
    if not settings.ENABLE_STRICT_RAG:
        return {
            "question": q,
            "answer": "G4 붉은 물때는 곰팡이가 아니라 박테리아입니다.",
        }

    result = await service.process_query(q)
    if not result["answer"]:
        return {
            "question": q,
            "answer": "검증된 도감 정보를 찾지 못했습니다.",
            "documents": [],
        }
    return result


@router.get("/query-safe")
async def search_safe_mold_info(q: str):
    """Verified dictionary-only query endpoint for the next app version."""
    result = await service.process_query(q)
    if not result["answer"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="검증된 도감 정보를 찾지 못했습니다.",
        )
    return result

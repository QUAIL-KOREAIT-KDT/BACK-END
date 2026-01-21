# BACK-END/domains/search/router.py

from fastapi import APIRouter
from app.domains.search.service import RAGService

router = APIRouter()
service = RAGService()

@router.get("/query")
async def search_mold_info(q: str):
    """[Source 13] RAG 기반 곰팡이 질의응답"""
    # answer = await service.process_query(q)
    return {"question": q, "answer": "G4 붉은 물때는 곰팡이가 아니라 박테리아입니다."}
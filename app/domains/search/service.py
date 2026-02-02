# BACK-END/app/domains/search/service.py
from app.domains.search.vector_store import vector_store
from app.domains.search.rag_engine import rag_engine
import logging

logger = logging.getLogger(__name__)

class SearchService:
    
    async def get_mold_solution_with_rag(self, mold_name: str, probability: float) -> dict:
        """
        RAG 파이프라인: [검색] -> [생성]
        """
        logger.info(f"🔎 RAG 프로세스 시작: {mold_name} (신뢰도: {probability}%)")

        # 1. Retrieve: 벡터 DB에서 관련 정보 검색
        # 유사도가 높은 상위 1개 문서만 참조
        search_results = vector_store.search(query=mold_name, n_results=1)
        
        context_text = ""
        # 검색 결과가 있는지 확인 (documents[0]이 리스트 형태임)
        if search_results and 'documents' in search_results and search_results['documents'] and len(search_results['documents'][0]) > 0:
            context_text = search_results['documents'][0][0]
            logger.info("✅ 관련 곰팡이 도감 정보 확보 완료")
        else:
            logger.warning("⚠️ DB에서 정확한 정보를 찾지 못했습니다. (Gemini 일반 지식 활용 예정)")
            context_text = "데이터베이스에 해당 곰팡이의 상세 정보가 없습니다. 일반적인 곰팡이 지식을 활용해 답변해주세요."

        # 2. Generate: Gemini가 리포트 작성
        rag_solution = await rag_engine.generate_diagnosis_report(
            mold_name=mold_name,
            probability=probability,
            context_text=context_text
        )

        return {
            "mold_name": mold_name,
            "probability": probability,
            "rag_solution": rag_solution
        }

search_service = SearchService()
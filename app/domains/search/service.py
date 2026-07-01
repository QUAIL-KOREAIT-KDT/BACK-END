# BACK-END/app/domains/search/service.py

import json
import logging

from app.core.config import settings
from app.domains.search.rag_engine import rag_engine
from app.domains.search.vector_store import vector_store

logger = logging.getLogger(__name__)


class SearchService:
    def _extract_documents(self, search_results) -> list[str]:
        if not search_results or not isinstance(search_results, dict):
            return []

        documents = search_results.get("documents") or []
        if not documents or not isinstance(documents[0], list):
            return []

        return [doc for doc in documents[0] if isinstance(doc, str) and doc.strip()]

    async def process_query(self, query: str) -> dict:
        """
        Verified dictionary search for the safe query endpoint.
        This returns only retrieved project knowledge, not LLM guesses.
        """
        search_results = vector_store.search(query=query, n_results=3)
        documents = self._extract_documents(search_results)

        if not documents:
            return {
                "question": query,
                "answer": None,
                "documents": [],
            }

        return {
            "question": query,
            "answer": "\n\n".join(documents),
            "documents": documents,
        }

    async def get_mold_solution_with_rag(self, mold_name: str, probability: float) -> dict:
        """
        RAG pipeline: retrieve dictionary context, then ask Gemini to write a report.
        Default behavior remains compatible with the released app. Strict evidence-only
        fallback is enabled only when ENABLE_STRICT_RAG=true.
        """
        logger.info("RAG process started: %s (%s%%)", mold_name, probability)

        search_results = vector_store.search(query=mold_name, n_results=1)
        documents = self._extract_documents(search_results)

        if documents:
            context_text = documents[0]
            logger.info("Mold dictionary context found")
        elif not settings.ENABLE_STRICT_RAG:
            logger.warning(
                "No exact dictionary context found. Keeping general Gemini fallback for released-app compatibility."
            )
            context_text = (
                "데이터베이스에 해당 곰팡이의 상세 정보가 없습니다. "
                "일반적인 곰팡이 지식을 활용해 답변해주세요."
            )
        else:
            logger.warning("No verified dictionary context found. Returning safe fallback.")
            fallback_solution = {
                "diagnosis": "검증된 도감 근거를 찾지 못해 상세 진단 리포트를 생성하지 않았습니다.",
                "FrequentlyVisitedAreas": [],
                "solution": ["사진을 다시 촬영하거나 관리자에게 도감 데이터 확인을 요청해주세요."],
                "prevention": ["실내 습도를 낮추고 환기를 유지해주세요."],
                "insight": "근거 없는 제거법 안내를 피하기 위해 일반 지식 기반 답변을 제한했습니다.",
            }
            return {
                "mold_name": mold_name,
                "probability": probability,
                "rag_solution": json.dumps(fallback_solution, ensure_ascii=False),
            }

        rag_solution = await rag_engine.generate_diagnosis_report(
            mold_name=mold_name,
            probability=probability,
            context_text=context_text,
        )

        return {
            "mold_name": mold_name,
            "probability": probability,
            "rag_solution": rag_solution,
        }


search_service = SearchService()

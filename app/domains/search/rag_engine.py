# BACK-END/app/domains/search/rag_engine.py
import google.generativeai as genai
from app.core.config import settings
import logging
import asyncio
import json
import time

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            'models/gemini-2.5-flash-lite',
            generation_config={"response_mime_type": "application/json"}
        )

    async def generate_diagnosis_report(self, mold_name: str, probability: float, context_text: str) -> str:
        start_time = time.time()
        
        # [로그 강화] 입력 Prompt 구성 (로그에 남길 내용)
        prompt = f"""
        당신은 건물 위생 및 곰팡이 관리 전문가 'QUAIL AI'입니다.
        아래 정보를 바탕으로 사용자에게 제공할 진단 리포트를 작성하세요.

        [이미지 분석 결과]
        - 발견된 곰팡이: {mold_name}
        - 분석 신뢰도: {probability:.1f}%

        [데이터베이스 참고 정보]
        {context_text}
        [절대 규칙]
        1. 반드시 아래 JSON Key 이름들을 정확히 지켜야 합니다. 다른 Key를 창조하지 마세요.
        2. 데이터가 없으면 "정보 없음"이라고 적더라도 Key는 유지하세요.

        [Target JSON Structure]
        {{
            "diagnosis": "String",
            "FrequentlyVisitedAreas": ["String", "String"],
            "solution": ["String", "String"],
            "prevention": ["String", "String"],
            "insight": "String"
        }}
        """

        try:
            # Gemini 호출
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            duration = time.time() - start_time

            # [핵심] 성공 시: 입력(Prompt 일부)과 출력(Response) 내용을 모두 기록
            # context_text가 너무 길 경우를 대비해 요약하거나, 디버깅을 위해 전체를 남길지 결정
            success_log = {
                "event": "GEMINI_SUCCESS",
                "target": mold_name,
                "duration": f"{duration:.3f}s",
                "input_context_preview": context_text[:200] + "..." if len(context_text) > 200 else context_text,
                "output_response": response.text  # 제미나이가 뱉은 전체 답변
            }
            logger.info(json.dumps(success_log, ensure_ascii=False))

            return response.text

        except Exception as e:
            duration = time.time() - start_time
            
            # [핵심] 실패 시: 에러 원인과 당시 입력 데이터 기록
            error_log = {
                "event": "GEMINI_FAILED",
                "target": mold_name,
                "duration": f"{duration:.3f}s",
                "error_cause": str(e), # 구체적인 에러 메시지
                "input_context": context_text # 실패 원인이 데이터 문제일 수 있으므로 기록
            }
            logger.error(json.dumps(error_log, ensure_ascii=False), exc_info=True)
            
            # Fallback 응답
            fallback_response = {
                "diagnosis": f"{mold_name}이(가) 의심됩니다. (AI 분석 지연)",
                "FrequentlyVisitedAreas": ["분석 불가"],
                "solution": ["기본 환기 및 청소 권장"],
                "prevention": ["습도 관리 요망"],
                "insight": "현재 상세 분석 서비스를 이용할 수 없습니다."
            }
            return json.dumps(fallback_response, ensure_ascii=False)

rag_engine = RAGEngine()
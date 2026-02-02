# BACK-END/app/domains/search/rag_engine.py
import google.generativeai as genai
from app.core.config import settings
import logging
import asyncio
import json

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        # API 키 설정
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # response_mime_type을 설정하면 모델이 강제로 JSON만 출력합니다.
        self.model = genai.GenerativeModel(
            'models/gemini-2.5-flash',
            generation_config={"response_mime_type": "application/json"}
        )

    async def generate_diagnosis_report(self, mold_name: str, probability: float, context_text: str) -> str:
        """
        검색된 곰팡이 지식(Context)과 시각 지능(YOLO) 결과를 결합하여
        JSON 포맷의 종합 진단 리포트를 생성합니다.
        """
        try:
            # [수정 2] 프롬프트 최적화
            prompt = f"""
            당신은 건물 위생 및 곰팡이 관리 전문가 'QUAIL AI'입니다.
            아래 정보를 바탕으로 사용자에게 제공할 진단 리포트를 작성하세요.

            [이미지 분석 결과]
            - 발견된 곰팡이: {mold_name}
            - 분석 신뢰도: {probability:.1f}%

            [데이터베이스 참고 정보]
            {context_text}

            [작성 규칙]
            1. 사용자의 주요 출몰 지역(FrequentlyVisitedAreas) 정보가 [참고 정보]에 있다면, 
               그 지역들에 맞춰서 'solution'과 'prevention' 배열의 순서를 1:1로 대응시켜 작성하세요.
            2. 모든 내용은 한국어로, 간결하고 명확하게 작성하세요.
            3. 불필요한 마크다운(```json 등)을 포함하지 말고 순수 JSON만 출력하세요.

            [출력 스키마 (JSON)]
            {{
                "diagnosis": "곰팡이의 정의, 발생 원인, 특징 요약 (한 문단)",
                "FrequentlyVisitedAreas": [
                    "주요 출몰 지역1",
                    "주요 출몰 지역2"
                ],
                "solution": [
                    "지역1에 대한 구체적 제거 방법",
                    "지역2에 대한 구체적 제거 방법"
                ],
                "prevention": [
                    "지역1에 대한 예방 가이드",
                    "지역2에 대한 예방 가이드"
                ],
                "insight": "AI 전문가 관점의 추가 조언 (건강 위험성, 시공 필요성 등)"
            }}
            """

            # 비동기적으로 Gemini 호출
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text

        except Exception as e:
            logger.error(f"Gemini 리포트 생성 실패: {e}")
            
            # [수정 3] 에러 발생 시에도 JSON 형식을 유지하여 프론트엔드 오류 방지
            fallback_response = {
                "diagnosis": f"{mold_name}이(가) 의심됩니다. (상세 분석 중 오류 발생)",
                "FrequentlyVisitedAreas": ["알 수 없음"],
                "solution": ["락스 희석액으로 닦아내고 충분히 환기시키세요."],
                "prevention": ["습도를 60% 이하로 유지하세요."],
                "insight": "현재 AI 서비스 연결 상태가 불안정하여 기본 답변을 제공합니다."
            }
            return json.dumps(fallback_response, ensure_ascii=False)

rag_engine = RAGEngine()
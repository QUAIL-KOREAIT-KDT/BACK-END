# BACK-END/app/domains/fortune/service.py

import json
import logging
import google.generativeai as genai
from app.core.config import settings

# 로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FortuneService:
    def __init__(self):
        try:
            # 설정 파일에서 API 키 로드
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            # 무료 티어에서 가장 빠르고 효율적인 모델 선택
            self.model = genai.GenerativeModel('models/gemini-2.5-flash')
            logger.info("Gemini API 설정 완료 (models/gemini-2.5-flash)")
        except Exception as e:
            # API 키가 없거나 설정 실패 시 로그 출력
            logger.error(f"Gemini 초기화 실패: {str(e)}")

    async def generate_pangi_fortune(self, user_question: str = None):
        """
        사용자 질문 수신 시 곰팡이 테마의 가족 페르소나로 답변 생성
        """
        if user_question:
            logger.info(f"질문 수신: {user_question}")
            system_instruction = (
                "당신은 '팡이'입니다. 모든 답변은 '곰팡이' 혹은 '주거 쾌적함'과 연결되어야 합니다. "
                "말투는 겉으로 무심하고 틱틱거리는 듯하나, 사실은 누구보다 질문자를 걱정하고 챙겨주는 "
                "츤데레 가족(아버지/어머니)의 느낌을 유지하세요. "
                "질문에 대해 직접적인 도움과 따뜻한 격려를 곰팡이 이야기에 섞어서 답변하세요."
            )
            prompt = f"{system_instruction}\n\n사용자 고민: {user_question}"
        else:
            logger.info("질문 없음: 기본 운세 모드")
            prompt = "주거 환경의 곰팡이와 쾌적함을 테마로 한 오늘의 운세를 작성하세요."

        final_prompt = (
            f"{prompt}\n\n"
            "반드시 아래의 JSON 형식을 지켜서 답변하세요. 다른 설명은 생략하세요.\n"
            "{\"score\": 0~100, \"status\": \"상태 요약\", \"message\": \"가족의 마음이 담긴 답변\"}"
        )

        try:
            logger.info("Gemini API 호출 시도 중...")
            # JSON 응답 강제 설정 (라이브러리 0.7.2+ 필요)
            response = self.model.generate_content(
                final_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            result = json.loads(response.text)
            logger.info("Gemini 응답 성공")
            return result

        except Exception as e:
            logger.error(f"FortuneService 오류: {str(e)}")
            return self._get_fallback_response()

    def _get_fallback_response(self):
        return {
            "score": 50,
            "status": "연결 흐림",
            "message": "서버에 포자가 날려 연결이 어렵구나. 밥 든든히 먹고 잠시 뒤에 다시 와라."
        }

fortune_service = FortuneService()
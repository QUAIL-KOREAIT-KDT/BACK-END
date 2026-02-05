# BACK-END/app/domains/diagnosis/service.py
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.storage import StorageClient
from app.domains.diagnosis.repository import DiagnosisRepository
from app.core.lifespan import ml_models  # 서버 시작 시 로드된 모델 재사용
from app.domains.search.service import search_service # [추가] RAG 서비스 임포트
import logging
import json
import io

logger = logging.getLogger(__name__)

# 예측 확률 임계치: 이 값 미만이면 "곰팡이 특정 불가"로 처리
CONFIDENCE_THRESHOLD = 60.0

class DiagnosisService:
    def __init__(self, db: AsyncSession):
        self.storage = StorageClient()
        self.repository = DiagnosisRepository(db)
        self.ai = ml_models["efficientnet"]  # lifespan에서 서버 시작 시 한 번만 로드된 인스턴스 재사용

    async def diagnose_image(self, file: UploadFile, place: str, user_id: int):
        # 파일 바이트를 먼저 메모리로 읽기 (S3 업로드 후 스트림이 닫히므로)
        file_bytes = await file.read()
        await file.seek(0)  # S3 업로드를 위해 포인터 초기화

        # 1. 이미지 S3 업로드
        image_url = await self.storage.upload_image(file)

        # 2. AI 모델(EfficientNet-B0) 분류 추론 (메모리의 바이트로 BytesIO 생성하여 전달)
        try:
            prediction = self.ai.predict(io.BytesIO(file_bytes))
            mold_name = prediction.get("class_name", "Unknown Mold")
            probability = float(prediction.get("confidence", 0.0))

        except Exception as e:
            logger.error(f"EfficientNet 추론 실패: {e}")
            mold_name = "Unknown"
            probability = 0.0

        # 3. 임계치 체크: 확률이 낮으면 곰팡이 특정 불가
        if probability < CONFIDENCE_THRESHOLD:
            mold_name = "UnClassified"
            # 프론트 RagSolution.parse와 동일한 JSON 구조로 반환
            final_solution = json.dumps({
                "diagnosis": "AI가 곰팡이를 특정하지 못했습니다. 이미지의 화질이 낮거나, 곰팡이가 아닌 오염물일 수 있습니다.",
                "FrequentlyVisitedAreas": [],
                "solution": [
                    "곰팡이 의심 부위를 가까이 접근하여 다시 사진을 찍어보세요.",
                    "밝은 빛 아래에서 촬영하세요.",
                    "반사가 심한 경우 각도를 바꿔 다시 시도해보세요."
                ],
                "prevention": [],
                "insight": "신뢰도가 낮아 정확한 곰팡이 종류를 판별할 수 없었습니다. 위의 권장 조치를 따라 다시 진단을 시도해주세요."
            }, ensure_ascii=False)
        else:
            # 4. G3 특별 처리: "물 테스트" 안내 추가
            if mold_name == "G3_WhiteMold":
                final_solution = await self._handle_g3_white_mold(mold_name, probability)
            else:
                # 기존 RAG 파이프라인 유지 (G1, G2, G4)
                rag_result = await search_service.get_mold_solution_with_rag(mold_name, probability)
                final_solution = rag_result["rag_solution"]

        # 5. DB 저장을 위한 데이터 구성
        # result 필드: "G1_Stachybotrys" → "G1" 등 등급 접두사만 저장 (프론트 표시용)
        # RAG 파이프라인에는 전체 클래스명을 사용하고, DB에는 등급만 저장
        grade = mold_name.split("_")[0]  # "G1_Stachybotrys" → "G1", "UnClassified" → "UnClassified"

        diagnosis_data = {
            "user_id": user_id,
            "image_path": image_url,
            "result": grade,              # 등급 접두사 (G1~G4 / UnClassified)
            "confidence": probability,    # 확률
            "mold_location": place,       # 발견 장소 (사용자 입력)
            "model_solution": final_solution # RAG가 생성한 리포트 저장
        }

        # 6. DB 저장
        saved_diagnosis = await self.repository.create_diagnosis(diagnosis_data)

        return saved_diagnosis

    async def _handle_g3_white_mold(self, mold_name: str, probability: float) -> str:
        """
        G3(흰곰팡이 + 백화현상) 특별 처리
        RAG JSON 응답의 insight 필드에 물 테스트 안내를 통합하여 반환
        """
        rag_result = await search_service.get_mold_solution_with_rag(mold_name, probability)
        rag_json_str = rag_result["rag_solution"]

        water_test_guide = (
            "\n\n[추가 진단 안내] 하얀 오염물이 판단되었습니다.\n"
            "이 오염물이 콘크리트 또는 벽돌 위에 있다면 간단한 테스트를 해보세요:\n"
            "→ 물을 약간 뿌려보세요.\n"
            "  • 물에 바로 녹으면 → 백화현상(소금기). 벽돌·콘크리트 내부의 수분이 건조할 때 표면으로 올라온 것입니다.\n"
            "  • 물이 맺혀서 바로 사라지지 않으면 → 곰팡이. 환기 및 제곰팡이 처리가 필요합니다."
        )

        try:
            rag_data = json.loads(rag_json_str)
            # insight 필드에 물 테스트 안내 추가 (JSON 구조 유지)
            rag_data["insight"] = rag_data.get("insight", "") + water_test_guide
            return json.dumps(rag_data, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # JSON 파싱 실패 시 문자열로 추가 (fallback)
            return rag_json_str + water_test_guide

# BACK-END/app/domains/diagnosis/service.py
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.storage import StorageClient
from app.domains.diagnosis.repository import DiagnosisRepository
from app.domains.diagnosis.ai_engine import YOLOEngine
from app.domains.search.service import search_service # [추가] RAG 서비스 임포트
import logging

logger = logging.getLogger(__name__)

class DiagnosisService:
    def __init__(self, db: AsyncSession):
        self.storage = StorageClient()
        self.repository = DiagnosisRepository(db)
        self.ai = YOLOEngine() # [활성화] YOLO 엔진 사용

    async def diagnose_image(self, file: UploadFile, place: str, user_id: int):
        # 1. 이미지 S3 업로드
        image_url = await self.storage.upload_image(file)
        
        # 2. AI 모델(YOLO) 추론
        try:
            # 실제 모델 예측 실행
            # (predict 함수가 {'class_name': str, 'confidence': float} 등을 반환한다고 가정)
            yolo_result = self.ai.predict(file.file) # file.file은 SpooledTemporaryFile
            
            mold_name = yolo_result.get("class_name", "Unknown Mold")
            probability = float(yolo_result.get("confidence", 0.0))
            
            # (테스트용) 모델이 아직 없거나 로드 실패 시 더미 데이터 사용 로직
            if mold_name == "Unknown": 
                 mold_name = "G1_Stachybotrys"
                 probability = 95.5

        except Exception as e:
            logger.error(f"YOLO 추론 실패 (기본값 사용): {e}")
            mold_name = "G1_Stachybotrys" # 테스트를 위한 기본값
            probability = 98.5

        # 3. RAG 기반 심층 진단 & 솔루션 생성 (Gemini Insight 포함)
        #    YOLO가 알려준 이름으로 DB를 뒤져서 상세 리포트를 받아옵니다.
        rag_result = await search_service.get_mold_solution_with_rag(mold_name, probability)
        
        final_solution = rag_result["rag_solution"]

        # 4. DB 저장을 위한 데이터 구성
        diagnosis_data = {
            "user_id": user_id,
            "image_path": image_url,
            "result": mold_name,          # 판별 결과 (이름)
            "confidence": probability,    # 확률
            "mold_location": place,       # 발견 장소 (사용자 입력)
            "model_solution": final_solution # [핵심] RAG가 생성한 긴 리포트 저장
        }
        
        # 5. DB 저장
        saved_diagnosis = await self.repository.create_diagnosis(diagnosis_data)
        
        return saved_diagnosis
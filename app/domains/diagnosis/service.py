# BACK-END/app/domains/diagnosis/service.py

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.storage import StorageClient
from app.domains.diagnosis.repository import DiagnosisRepository
from app.domains.diagnosis.ai_engine import YOLOEngine

class DiagnosisService:
    def __init__(self, db: AsyncSession):
        self.storage = StorageClient()
        self.repository = DiagnosisRepository(db)
        # self.ai = YOLOEngine()

    async def diagnose_image(self, file: UploadFile, place: str, user_id: int):
        # 1. 이미지 S3 업로드
        image_url = await self.storage.upload_image(file)
        
        # 2. [Source 7] AI 모델 추론
        # result = self.ai.predict(file)
        
        # 3. [Source 8, 12] 결과 매칭 (G1 -> 락스 사용하세요)
        # 4. DB에 진단 기록(Logs) 저장

        # 2. AI 모델 추론 (더미 데이터)
        ai_result = {
            "result": "G1_Cladosporium",
            "confidence": 0.95,
            "model_solution": "락스 희석액을 사용하여 닦아내고 충분히 환기하세요."
        }
        
        # 3. DB 저장을 위한 데이터 구성
        diagnosis_data = {
            "user_id": user_id,
            "image_path": image_url,
            "result": ai_result["result"],
            "confidence": ai_result["confidence"],
            "mold_location": place,
            "model_solution": ai_result["model_solution"]
        }
        
        # 4. DB 저장
        saved_diagnosis = await self.repository.create_diagnosis(diagnosis_data)
        
        return saved_diagnosis
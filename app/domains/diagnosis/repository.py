# BACK-END/app/domains/diagnosis/repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.diagnosis.models import Diagnosis

class DiagnosisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_diagnosis(self, diagnosis_data: dict) -> Diagnosis:
        """진단 결과를 DB에 저장합니다."""
        new_diagnosis = Diagnosis(
            user_id=diagnosis_data['user_id'],
            result=diagnosis_data['result'],
            confidence=diagnosis_data['confidence'],
            image_path=diagnosis_data['image_path'],
            mold_location=diagnosis_data['mold_location'],
            model_solution=diagnosis_data['model_solution']
        )
        
        self.db.add(new_diagnosis)
        await self.db.commit()
        await self.db.refresh(new_diagnosis)
        
        return new_diagnosis
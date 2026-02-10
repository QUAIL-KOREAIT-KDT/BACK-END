# BACK-END/app/domains/diagnosis/repository.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.diagnosis.models import Diagnosis
from sqlalchemy import select, delete

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
            gradcam_image_path=diagnosis_data.get('gradcam_image_path'),
            bbox_coordinates=diagnosis_data.get('bbox_coordinates'),
            mold_location=diagnosis_data['mold_location'],
            model_solution=diagnosis_data['model_solution']
        )
        
        self.db.add(new_diagnosis)
        await self.db.commit()
        await self.db.refresh(new_diagnosis)
        
        return new_diagnosis
    
    async def get_diagnosis_by_user_id(self, db, user_id: int) -> list[Diagnosis]:
        query = select(Diagnosis).where(Diagnosis.user_id == user_id).order_by(Diagnosis.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()
    # select * from Diagnosis where 컬럼user_id = 변수user_id and 컬럼id = 변수id
    

    async def delete_diagnosis_info(self, db, id: int):
        stmt = delete(Diagnosis).where(Diagnosis.id == id)
        await db.execute(stmt)
        await db.commit()
        return True
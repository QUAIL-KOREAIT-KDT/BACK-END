from requests import delete
from app.domains.diagnosis.models import Diagnosis
from app.domains.diagnosis.repository import DiagnosisRepository

class MyPageService:
    def __init__(self, db):
        self.repo = DiagnosisRepository(db)

    async def get_diagnosis_records(self, db, user_id):
        """곰팡이 진단 기록정보 받아오기"""
        records = await self.repo.get_diagnosis_by_user_id(db, user_id)
        return [
                {
                "id": record.id,
                "image_path": record.image_path,
                "gradcam_image_path": record.gradcam_image_path,
                "created_at": record.created_at,
                "result": record.result,
                "mold_location": record.mold_location
                } for record in records]


    async def get_diagnosis_info(self,db, user_id, id):
        """진단 상세 정보 받아오기"""
        records = await self.repo.get_diagnosis_by_user_id(db, user_id)
        for record in records:
            if record.id == id.id:
                return record
        return None
    

    async def delete_diagnosis_record(self, db, id: int):
        """진단 기록 삭제"""
        result = await self.repo.delete_diagnosis_info(db, id)
        return result
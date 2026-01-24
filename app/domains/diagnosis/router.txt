# BACK-END/app/domains/diagnosis/router.py

from fastapi import APIRouter, UploadFile, File
from app.domains.diagnosis.service import DiagnosisService

router = APIRouter()
service = DiagnosisService()

@router.post("/predict")
async def predict_mold(file: UploadFile = File(...)):
    """[Source 4] 곰팡이 사진 업로드 및 판별 결과 반환"""
    await service.diagnose_image(file)
    # [Source 8] 더미 결과
    return {
        "mold_name": "Cladosporium (검은 곰팡이)",
        "code": "G1",
        "solution": "락스 희석액을 사용하여 닦아내세요.",
        "image_url": "https://s3..."
    }
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.my_page.service import MyPageService
from app.domains.my_page.schemas import DiagnosisInfo, DiagnosisOutput, Thumbnail
router = APIRouter()

# 1. 곰팡이 진단 기록정보 받아오기
@router.get("/diagnosis-history",response_model=List[Thumbnail])
async def get_diagnosis_records(
    user_id: int = Depends(verify_token), 
    db: AsyncSession = Depends(get_db)
):
    service = MyPageService(db)
    return await service.get_diagnosis_records(db, user_id)

# 2. 진단 상세 정보(입출력스키마둘다받아옴)
@router.post("/diagnosis-info/",response_model=DiagnosisOutput)
async def get_diagnosis_info(
    id: DiagnosisInfo,
    userid: int= Depends(verify_token),
    db: AsyncSession = Depends(get_db)
    ):
    service = MyPageService(db)
    result = await service.get_diagnosis_info(db, userid, id)
    return {
        "id": result.id,
        "user_id": result.user_id,
        "result": result.result,
        "confidence": result.confidence,
        "image_path": result.image_path,
        "mold_location": result.mold_location,
        "created_at": result.created_at,
        "model_solution": result.model_solution,
    }

@router.delete("/delete-diagnosis/")
async def delete_diagnosis_record(
    id: DiagnosisInfo,
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    service = MyPageService(db)
    await service.delete_diagnosis_record(db,id.id)
    # 삭제 로직 구현 필요
    return {"message": "삭제되었긔"}
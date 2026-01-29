# BACK-END/app/domains/diagnosis/router.py

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.domains.auth.jwt_handler import verify_token
from app.domains.diagnosis.service import DiagnosisService
from app.domains.diagnosis.schemas import DiagnosisResponse

from enum import Enum as PyEnum

router = APIRouter()

class MoldLocation(str, PyEnum):
    WINDOWS = "windows"
    WALLPAPER = "wallpaper"
    BATHROOM = "bathroom"
    CEILING = "ceiling"
    KITCHEN = "kitchen"
    FOOD = "food"
    VERANDA = "veranda"
    AIR_CONDITIONER = "air_conditioner"
    LIVING_ROOM = "living_room"
    SINK = "sink"
    TOILET = "toilet"
    
@router.post("/predict", response_model=DiagnosisResponse)
async def predict_mold(
    file: UploadFile = File(...),      # 파일은 File로 받기
    place: MoldLocation = Form(...),           # 텍스트는 Form으로 받기
    user_id: int = Depends(verify_token),
    db: AsyncSession = Depends(get_db)
):
    """
    [Source 4] 곰팡이 사진 업로드 및 판별
    - file: 업로드할 이미지 파일
    - place: 곰팡이 발생 장소 (예: wallpaper, bathroom 등)
    """
    # 1. 파일 형식 검사
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미지 파일만 업로드할 수 있습니다."
        )

    # 2. 서비스 로직 실행
    service = DiagnosisService(db)
    
    # place 정보도 함께 넘겨줍니다.
    result = await service.diagnose_image(file, place.value, user_id)
    
    return result


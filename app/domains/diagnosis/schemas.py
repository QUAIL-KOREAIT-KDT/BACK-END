# BACK-END/app/domains/diagnosis/schemas.py
from pydantic import BaseModel
from datetime import datetime

# =============출력==============
class DiagnosisResponse(BaseModel):
    id: int
    result: str
    confidence: float
    image_path: str
    mold_location: str
    created_at: datetime
    model_solution: str

    class Config:
        from_attributes = True  # ORM 객체를 Pydantic 모델로 변환 허용


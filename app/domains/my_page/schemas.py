# BACK-END/app/domains/My_Page/schemas.py
from datetime import datetime
from pydantic import BaseModel

# 입력
class DiagnosisInfo(BaseModel):
    id: int

# 출력
class DiagnosisOutput(BaseModel):
    id: int
    user_id: int
    result: str
    confidence: float
    image_path: str
    gradcam_image_path: str | None = None
    mold_location: str
    created_at: datetime
    model_solution: str

class Thumbnail(BaseModel):
    id: int
    image_path: str
    gradcam_image_path: str | None = None
    created_at: datetime
    result: str = ''
    mold_location: str = ''


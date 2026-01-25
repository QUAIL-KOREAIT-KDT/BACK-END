# BACK-END/app/domains/dictionary/schemas.py

from pydantic import BaseModel
from typing import Optional

class DictionaryResponse(BaseModel):
    id: int
    label: str          # G1~G8
    name: str           # 곰팡이 이름
    feature: str        # 특징 (text)
    location: str       # 서식 위치 (Enum이지만 문자열로 반환)
    image_path: str     # 썸네일
    detail_image_path: str # 상세 이미지
    solution: str       # 처리 방법
    preventive: str     # 예방법

    class Config:
        from_attributes = True # DB 모델을 Pydantic 모델로 자동 변환
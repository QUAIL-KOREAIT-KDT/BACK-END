from datetime import datetime
from typing import Any

from pydantic import BaseModel


class KakaoAuthorizeUrlResponse(BaseModel):
    authorize_url: str
    state: str | None = None


class KakaoCodeLoginRequest(BaseModel):
    code: str
    redirect_uri: str


class WebDictionaryItem(BaseModel):
    id: int
    label: str
    name: str
    feature: str
    location: str
    image_path: str
    detail_image_path: str
    solution: str
    preventive: str

    class Config:
        from_attributes = True


class WebDashboardResponse(BaseModel):
    profile: dict[str, Any]
    diagnosis_history: list[dict[str, Any]]
    game: dict[str, Any]
    notification_settings: dict[str, Any]
    summary: dict[str, Any]


class WebDiagnosisResult(BaseModel):
    id: int
    result: str
    confidence: float
    image_path: str
    gradcam_image_path: str | None = None
    bbox_coordinates: str | None = None
    mold_location: str
    created_at: datetime
    model_solution: str
    web_next: dict[str, str]

    class Config:
        from_attributes = True
